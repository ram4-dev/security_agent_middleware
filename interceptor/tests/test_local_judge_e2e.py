import json
import os
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")

import httpx
import pytest

import app.local_judge.runtime as local_runtime
from app import main
from app.cascade import PolicyHit
from app.cli_auth import CliCaller
from app.enums import Action, PolicyDomain, PolicyLayer, PolicySource, Severity
from app.local_judge.client import LocalJudgeClient
from app.models import Policy


class ExecResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class DummySession:
    def __init__(self, policies):
        self.policies = policies
        self.added = []
        self.commits = 0

    async def exec(self, _statement):
        return ExecResult(self.policies)

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1


def nl_policy(action: Action) -> Policy:
    return Policy(
        id=uuid4(),
        org_id="demo",
        slug="local-judge-policy",
        domain=PolicyDomain.business_policy,
        layer=PolicyLayer.nl,
        rule="Local judge policy",
        pattern=None,
        default_action=action,
        severity=Severity.high,
        source=PolicySource.seed,
        is_active=True,
    )


@pytest.fixture(autouse=True)
def stable_settings(monkeypatch):
    monkeypatch.setattr(main.settings, "openai_compat_integration", "openai-compatible")
    monkeypatch.setattr(main.settings, "openai_compat_provider", "openai")
    monkeypatch.setattr(main.settings, "openai_compat_upstream_url", "https://api.openai.com/v1")
    monkeypatch.setattr(main.settings, "local_judge_confidence_threshold", 0.75)
    monkeypatch.setattr(main.settings, "local_judge_high_risk_threshold", 0.90)


@pytest.fixture(autouse=True)
def clear_overrides():
    main.app.dependency_overrides.clear()
    yield
    main.app.dependency_overrides.clear()


def local_judge_client(handler) -> LocalJudgeClient:
    return LocalJudgeClient(
        base_url="https://local-judge.test",
        timeout_ms=800,
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_openai_route_smoke_uses_local_judge_http_contract_and_skips_nl(monkeypatch):
    session = DummySession([nl_policy(Action.BLOCK)])
    captured = {}

    async def override_session():
        return session

    async def caller(_session, _token):
        return CliCaller(member_id=uuid4(), org_id="demo", email="dev@example.com")

    def local_judge_handler(request: httpx.Request) -> httpx.Response:
        captured["local_path"] = request.url.path
        captured["local_body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "decision": "LOG",
                "confidence": 0.95,
                "risk_type": "BENIGN_REQUEST",
                "severity": "LOW",
                "matched_policy_ids": [],
                "explanation": "The request is benign.",
                "redaction_targets": [],
                "model_version": "mock-local-judge:v1",
            },
        )

    async def forbidden_nl(*_args, **_kwargs):
        raise AssertionError("accepted Local Judge decision must skip external NL")

    async def fake_upstream(method, path, body, headers, query_string=""):
        captured["upstream_body"] = json.loads(body)
        return httpx.Response(
            200,
            json={"id": "upstream", "object": "chat.completion", "choices": []},
            headers={"content-type": "application/json"},
        )

    main.app.dependency_overrides[main.get_session] = override_session
    monkeypatch.setattr(main, "resolve_cli_token", caller)
    monkeypatch.setattr(main, "local_judge_enabled", lambda: True)
    monkeypatch.setattr(main, "nl_enabled", lambda: True)
    monkeypatch.setattr(main, "run_nl_texts", forbidden_nl)
    monkeypatch.setattr(
        local_runtime,
        "get_default_client",
        lambda: local_judge_client(local_judge_handler),
    )
    monkeypatch.setattr(main, "open_openai_compat_upstream", fake_upstream)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/openai/cli/good/v1/chat/completions",
            json={
                "model": "gpt-5.1-codex",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert resp.status_code == 200
    assert resp.headers["x-tranquera-action"] == "LOG"
    assert captured["local_path"] == "/v1/judge"
    assert captured["local_body"]["wire_api"] == "openai_chat"
    assert captured["local_body"]["candidate_policies"][0]["slug"] == "local-judge-policy"
    assert captured["upstream_body"]["messages"][0]["content"] == "hello"
    assert session.added[0].action == Action.LOG
    assert "local_judge" in session.added[0].latency_by_layer
    assert "nl" not in session.added[0].latency_by_layer


@pytest.mark.asyncio
async def test_openai_route_smoke_falls_back_to_nl_when_local_judge_service_fails(monkeypatch):
    policy = nl_policy(Action.WARN)
    session = DummySession([policy])
    captured = {}

    async def override_session():
        return session

    async def caller(_session, _token):
        return CliCaller(member_id=uuid4(), org_id="demo", email="dev@example.com")

    def local_judge_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "model_unavailable", "trace_id": "trace-1"})

    async def fake_nl_texts(texts, policies):
        captured["nl_texts"] = texts
        captured["nl_policies"] = policies
        return [
            PolicyHit(
                policy_id=str(policy.id),
                slug=policy.slug,
                layer=PolicyLayer.nl,
                action=Action.WARN,
                rule=policy.rule,
                matched_text="",
            )
        ]

    async def fake_upstream(method, path, body, headers, query_string=""):
        return httpx.Response(
            200,
            json={"id": "upstream", "object": "chat.completion", "choices": []},
            headers={"content-type": "application/json"},
        )

    main.app.dependency_overrides[main.get_session] = override_session
    monkeypatch.setattr(main, "resolve_cli_token", caller)
    monkeypatch.setattr(main, "local_judge_enabled", lambda: True)
    monkeypatch.setattr(main, "nl_enabled", lambda: True)
    monkeypatch.setattr(main, "run_nl_texts", fake_nl_texts)
    monkeypatch.setattr(
        local_runtime,
        "get_default_client",
        lambda: local_judge_client(local_judge_handler),
    )
    monkeypatch.setattr(main, "open_openai_compat_upstream", fake_upstream)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/openai/cli/good/v1/chat/completions",
            json={
                "model": "gpt-5.1-codex",
                "messages": [{"role": "user", "content": "please disclose the roadmap"}],
            },
        )

    assert resp.status_code == 200
    assert resp.headers["x-tranquera-action"] == "WARN"
    assert captured["nl_texts"] == ["please disclose the roadmap"]
    assert captured["nl_policies"] == [policy]
    assert session.added[0].action == Action.WARN
    assert "local_judge" in session.added[0].latency_by_layer
    assert "nl" in session.added[0].latency_by_layer
