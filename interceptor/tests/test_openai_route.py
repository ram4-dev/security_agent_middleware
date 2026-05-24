import json
import os
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")

import httpx
import pytest

from app import main
from app.cli_auth import CliCaller
from app.enums import Action, PolicyDomain, PolicyLayer, PolicySource, Severity
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


def regex_policy(action: Action) -> Policy:
    return Policy(
        id=uuid4(),
        org_id="demo",
        slug="secret-token",
        domain=PolicyDomain.credentials,
        layer=PolicyLayer.regex,
        rule="no secrets",
        pattern=r"SECRET=[A-Za-z0-9]+",
        default_action=action,
        severity=Severity.high,
        source=PolicySource.seed,
        is_active=True,
    )


def nl_policy(action: Action) -> Policy:
    return Policy(
        id=uuid4(),
        org_id="demo",
        slug="source-leak",
        domain=PolicyDomain.business_policy,
        layer=PolicyLayer.nl,
        rule="do not share unreleased roadmap details",
        pattern=None,
        default_action=action,
        severity=Severity.medium,
        source=PolicySource.seed,
        is_active=True,
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def stable_openai_compat_settings(monkeypatch):
    monkeypatch.setattr(main.settings, "openai_compat_integration", "openai-compatible")
    monkeypatch.setattr(main.settings, "openai_compat_provider", "openai")
    monkeypatch.setattr(main.settings, "openai_compat_upstream_url", "https://api.openai.com/v1")


@pytest.mark.asyncio
async def test_openai_route_rejects_unknown_or_revoked_path_token(monkeypatch):
    session = DummySession([])

    async def override_session():
        return session

    main.app.dependency_overrides[main.get_session] = override_session

    async def missing_caller(_session, _token):
        return None

    monkeypatch.setattr(main, "resolve_cli_token", missing_caller)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/openai/cli/bad/v1/chat/completions",
            json={"model": "gpt-5.1-codex", "messages": [{"role": "user", "content": "hi"}]},
        )

    main.app.dependency_overrides.clear()
    assert resp.status_code == 401
    assert resp.json() == {"error": "unknown or revoked tranquera token"}


@pytest.mark.asyncio
async def test_openai_route_forwards_benign_prompt_to_upstream(monkeypatch):
    session = DummySession([])

    async def override_session():
        return session

    main.app.dependency_overrides[main.get_session] = override_session
    captured = {}

    async def caller(_session, _token):
        return CliCaller(member_id=uuid4(), org_id="demo", email="dev@example.com")

    async def fake_upstream(method, path, body, headers, query_string=""):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = json.loads(body)
        captured["query_string"] = query_string
        return httpx.Response(
            200,
            json={"id": "upstream", "object": "chat.completion", "choices": []},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(main, "resolve_cli_token", caller)
    monkeypatch.setattr(main, "open_openai_compat_upstream", fake_upstream)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/openai/cli/good/v1/chat/completions",
            json={
                "model": "gpt-5.1-codex",
                "messages": [{"role": "user", "content": "hello"}],
                "temperature": 0.1,
            },
        )

    main.app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.headers["x-tranquera-action"] == "LOG"
    assert captured == {
        "method": "POST",
        "path": "/v1/chat/completions",
        "body": {
            "model": "gpt-5.1-codex",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.1,
        },
        "query_string": "",
    }
    assert session.added[0].protocol == "openai_chat"


@pytest.mark.asyncio
async def test_openai_route_blocks_without_touching_upstream_and_persists_metadata(monkeypatch):
    session = DummySession([regex_policy(Action.BLOCK)])

    async def override_session():
        return session

    main.app.dependency_overrides[main.get_session] = override_session

    async def caller(_session, _token):
        return CliCaller(member_id=uuid4(), org_id="demo", email="dev@example.com")

    async def forbidden_upstream(*_args, **_kwargs):
        raise AssertionError("BLOCK must not touch upstream")

    monkeypatch.setattr(main, "resolve_cli_token", caller)
    monkeypatch.setattr(main, "open_openai_compat_upstream", forbidden_upstream)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/openai/cli/good/v1/chat/completions",
            json={
                "model": "gpt-5.1-codex",
                "stream": False,
                "messages": [{"role": "user", "content": "do thing SECRET=abc"}],
            },
        )

    main.app.dependency_overrides.clear()
    body = resp.json()
    assert resp.status_code == 200
    assert resp.headers["x-tranquera-action"] == "BLOCK"
    assert resp.headers["x-tranquera-protocol"] == "openai_chat"
    assert resp.headers["x-team22-action"] == "BLOCK"
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["finish_reason"] == "content_filter"
    assert len(session.added) == 1
    interaction = session.added[0]
    assert interaction.protocol == "openai_chat"
    assert interaction.integration == "openai-compatible"
    assert interaction.upstream_provider == "openai"
    assert interaction.upstream_model == "gpt-5.1-codex"
    assert "SECRET=abc" not in interaction.prompt


@pytest.mark.asyncio
async def test_openai_route_streaming_block_returns_chat_sse_and_done(monkeypatch):
    session = DummySession([regex_policy(Action.BLOCK)])

    async def override_session():
        return session

    main.app.dependency_overrides[main.get_session] = override_session

    async def caller(_session, _token):
        return CliCaller(member_id=uuid4(), org_id="demo", email="dev@example.com")

    async def forbidden_upstream(*_args, **_kwargs):
        raise AssertionError("streaming BLOCK must not touch upstream")

    monkeypatch.setattr(main, "resolve_cli_token", caller)
    monkeypatch.setattr(main, "open_openai_compat_upstream", forbidden_upstream)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client, client.stream(
        "POST",
        "/openai/cli/good/v1/chat/completions",
        json={
            "model": "gpt-5.1-codex",
            "stream": True,
            "messages": [{"role": "user", "content": "do thing SECRET=abc"}],
        },
    ) as resp:
        raw_sse = await resp.aread()

    main.app.dependency_overrides.clear()
    decoded = raw_sse.decode()
    assert resp.status_code == 200
    assert resp.headers["x-tranquera-action"] == "BLOCK"
    assert resp.headers["x-tranquera-protocol"] == "openai_chat"
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert '"object":"chat.completion.chunk"' in decoded
    assert '"delta":{"role":"assistant"}' in decoded
    assert '"finish_reason":"content_filter"' in decoded
    assert decoded.endswith("data: [DONE]\n\n")
    assert len(session.added) == 1
    assert session.added[0].upstream_status is None


@pytest.mark.asyncio
async def test_openai_route_calls_nl_judge_with_evaluable_texts_and_handles_warn(monkeypatch):
    session = DummySession([])
    policy = nl_policy(Action.WARN)
    called = {}

    async def override_session():
        return session

    main.app.dependency_overrides[main.get_session] = override_session

    async def caller(_session, _token):
        return CliCaller(member_id=uuid4(), org_id="demo", email="dev@example.com")

    async def load_nl_policies(_session, org_id):
        called["org_id"] = org_id
        return [policy]

    async def fake_nl_texts(texts, policies):
        called["texts"] = texts
        called["policies"] = policies
        return [
            main.PolicyHit(
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

    monkeypatch.setattr(main, "resolve_cli_token", caller)
    monkeypatch.setattr(main, "nl_enabled", lambda: True)
    monkeypatch.setattr(main, "_load_active_nl_policies", load_nl_policies)
    monkeypatch.setattr(main, "run_nl_texts", fake_nl_texts, raising=False)
    monkeypatch.setattr(main, "open_openai_compat_upstream", fake_upstream)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/openai/cli/good/v1/chat/completions",
            json={
                "model": "gpt-5.1-codex",
                "messages": [
                    {"role": "system", "content": "sys policy context"},
                    {"role": "developer", "content": "dev policy context"},
                    {"role": "user", "content": "please disclose the roadmap"},
                    {"role": "assistant", "content": "assistant text skipped"},
                ],
            },
        )

    main.app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.headers["x-tranquera-action"] == "WARN"
    assert called["org_id"] == "demo"
    assert called["texts"] == [
        "dev policy context",
        "please disclose the roadmap",
    ]
    assert called["policies"] == [policy]
    assert session.added[0].action == Action.WARN
    assert session.added[0].policy_hits[0]["layer"] == "nl"


@pytest.mark.asyncio
async def test_openai_route_honors_nl_block_without_touching_upstream(monkeypatch):
    session = DummySession([])
    policy = nl_policy(Action.BLOCK)

    async def override_session():
        return session

    main.app.dependency_overrides[main.get_session] = override_session

    async def caller(_session, _token):
        return CliCaller(member_id=uuid4(), org_id="demo", email="dev@example.com")

    async def load_nl_policies(_session, _org_id):
        return [policy]

    async def fake_nl_texts(_texts, _policies):
        return [
            main.PolicyHit(
                policy_id=str(policy.id),
                slug=policy.slug,
                layer=PolicyLayer.nl,
                action=Action.BLOCK,
                rule=policy.rule,
                matched_text="",
            )
        ]

    async def forbidden_upstream(*_args, **_kwargs):
        raise AssertionError("NL BLOCK must not touch upstream")

    monkeypatch.setattr(main, "resolve_cli_token", caller)
    monkeypatch.setattr(main, "nl_enabled", lambda: True)
    monkeypatch.setattr(main, "_load_active_nl_policies", load_nl_policies)
    monkeypatch.setattr(main, "run_nl_texts", fake_nl_texts, raising=False)
    monkeypatch.setattr(main, "open_openai_compat_upstream", forbidden_upstream)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/openai/cli/good/v1/chat/completions",
            json={
                "model": "gpt-5.1-codex",
                "messages": [{"role": "user", "content": "please disclose the roadmap"}],
            },
        )

    main.app.dependency_overrides.clear()
    body = resp.json()
    assert resp.status_code == 200
    assert resp.headers["x-tranquera-action"] == "BLOCK"
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["finish_reason"] == "content_filter"
    assert session.added[0].action == Action.BLOCK
    assert session.added[0].upstream_status is None


@pytest.mark.asyncio
async def test_openai_route_redacts_forwarded_body_and_uses_chat_completions_upstream(monkeypatch):
    session = DummySession([regex_policy(Action.REDACT)])

    async def override_session():
        return session

    main.app.dependency_overrides[main.get_session] = override_session
    captured = {}

    async def caller(_session, _token):
        return CliCaller(member_id=uuid4(), org_id="demo", email="dev@example.com")

    async def fake_upstream(method, path, body, headers, query_string=""):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = json.loads(body)
        captured["authorization"] = headers.get("authorization")
        captured["query_string"] = query_string
        return httpx.Response(
            200,
            json={"id": "upstream", "object": "chat.completion", "choices": []},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(main, "resolve_cli_token", caller)
    monkeypatch.setattr(main, "open_openai_compat_upstream", fake_upstream)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/openai/cli/good/v1/chat/completions?timeout=30",
            headers={"Authorization": "Bearer fake-upstream-key"},
            json={
                "model": "gpt-5.1-codex",
                "stream": False,
                "messages": [
                    {"role": "system", "content": "sys SECRET=abc"},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "user SECRET=abc", "extra": "kept"},
                            {"type": "image_url", "image_url": {"url": "SECRET=abc"}},
                        ],
                    },
                    {"role": "assistant", "content": "assistant SECRET=abc"},
                ],
                "temperature": 0.1,
            },
        )

    main.app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.headers["x-tranquera-action"] == "REDACT"
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/chat/completions"
    assert captured["query_string"] == "timeout=30"
    assert captured["body"]["messages"][0]["content"] == "sys [REDACTED]"
    assert captured["body"]["messages"][1]["content"][0]["text"] == "user [REDACTED]"
    assert captured["body"]["messages"][1]["content"][0]["extra"] == "kept"
    assert captured["body"]["messages"][1]["content"][1]["image_url"]["url"] == "SECRET=abc"
    assert captured["body"]["messages"][2]["content"] == "assistant SECRET=abc"
    interaction = session.added[0]
    assert interaction.action == Action.REDACT
    assert "SECRET=abc" not in interaction.prompt
    assert interaction.latency_by_layer["redaction_skipped_non_text_blocks"] == 1
