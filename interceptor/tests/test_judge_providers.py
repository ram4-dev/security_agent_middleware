import json
import os
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")

import httpx
import pytest

import app.nl_layer as nl_layer
from app.cascade import run_regex_texts
from app.enums import Action, PolicyDomain, PolicyLayer, PolicySource, Severity
from app.judge.anthropic import AnthropicJudgeProvider
from app.judge.factory import DisabledJudgeProvider, get_judge_provider
from app.judge.gemini import GeminiJudgeProvider
from app.judge.openai_compatible import OpenAICompatibleJudgeProvider
from app.judge.prompt import parse_matched_ids
from app.judge.types import JudgeDecision, JudgeRequest
from app.models import Policy


def make_policy(*, layer: PolicyLayer = PolicyLayer.nl, pattern: str | None = None) -> Policy:
    return Policy(
        id=uuid4(),
        org_id="demo",
        slug="source-leak",
        domain=PolicyDomain.business_policy,
        layer=layer,
        rule="do not share unreleased roadmap details",
        pattern=pattern,
        default_action=Action.BLOCK,
        severity=Severity.medium,
        source=PolicySource.seed,
        is_active=True,
    )


def judge_request(policy: Policy) -> JudgeRequest:
    return JudgeRequest(
        trace_id="trace-1",
        org_id="demo",
        texts=["share the unreleased roadmap"],
        policies=[policy],
    )


@pytest.mark.parametrize(
    "raw",
    [
        '{"matched": ["p1"]}',
        '```json\n{"matched": ["p1"]}\n```',
        'prefix {"matched": ["p1"]} suffix',
        'noise {"ignored": true} then {"matched": ["p1"]}',
    ],
)
def test_parse_matched_ids_tolerates_json_noise(raw):
    assert parse_matched_ids(raw) == ["p1"]


@pytest.mark.asyncio
async def test_anthropic_provider_posts_messages_and_returns_policy_ids():
    policy = make_policy()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["api_key"] = request.headers["x-api-key"]
        body = json.loads(request.content)
        captured["model"] = body["model"]
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": json.dumps({"matched": [str(policy.id)]})}]},
        )

    provider = AnthropicJudgeProvider(
        api_key="test-key",
        base_url="https://anthropic.test",
        model="claude-test",
        transport=httpx.MockTransport(handler),
    )

    decision = await provider.judge(judge_request(policy))

    assert captured == {"path": "/v1/messages", "api_key": "test-key", "model": "claude-test"}
    assert decision.matched_policy_ids == [str(policy.id)]


@pytest.mark.parametrize("provider_name", ["opencode-go", "openai"])
@pytest.mark.asyncio
async def test_openai_compatible_provider_posts_chat_completions(provider_name):
    policy = make_policy()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers["authorization"]
        body = json.loads(request.content)
        captured["stream"] = body["stream"]
        captured["roles"] = [message["role"] for message in body["messages"]]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"matched": [str(policy.id)]})}}]},
        )

    provider = OpenAICompatibleJudgeProvider(
        provider=provider_name,
        api_key="test-key",
        base_url="https://llm.test/v1",
        model="judge-model",
        transport=httpx.MockTransport(handler),
    )

    decision = await provider.judge(judge_request(policy))

    assert captured == {
        "path": "/v1/chat/completions",
        "auth": "Bearer test-key",
        "stream": False,
        "roles": ["system", "user"],
    }
    assert decision.matched_policy_ids == [str(policy.id)]


@pytest.mark.asyncio
async def test_gemini_provider_posts_generate_content_and_returns_policy_ids():
    policy = make_policy()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["query"] = request.url.query.decode()
        body = json.loads(request.content)
        captured["mime"] = body["generationConfig"]["responseMimeType"]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": f'```json\\n{{"matched": ["{policy.id}"]}}\\n```'}]
                        }
                    }
                ]
            },
        )

    provider = GeminiJudgeProvider(
        api_key="test-key",
        base_url="https://gemini.test/v1beta",
        model="gemini-test",
        transport=httpx.MockTransport(handler),
    )

    decision = await provider.judge(judge_request(policy))

    assert captured == {
        "path": "/v1beta/models/gemini-test:generateContent",
        "query": "key=test-key",
        "mime": "application/json",
    }
    assert decision.matched_policy_ids == [str(policy.id)]


@pytest.mark.parametrize("status_code", [401, 500])
@pytest.mark.asyncio
async def test_provider_fail_open_on_non_200(status_code):
    policy = make_policy()

    provider = OpenAICompatibleJudgeProvider(
        provider="openai",
        api_key="test-key",
        base_url="https://llm.test/v1",
        model="judge-model",
        transport=httpx.MockTransport(lambda _request: httpx.Response(status_code, text="nope")),
    )

    decision = await provider.judge(judge_request(policy))

    assert decision.matched_policy_ids == []


@pytest.mark.asyncio
async def test_provider_fail_open_on_timeout_and_malformed_json():
    policy = make_policy()

    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    timeout_provider = OpenAICompatibleJudgeProvider(
        provider="openai",
        api_key="test-key",
        base_url="https://llm.test/v1",
        model="judge-model",
        transport=httpx.MockTransport(timeout),
    )
    malformed_provider = OpenAICompatibleJudgeProvider(
        provider="openai",
        api_key="test-key",
        base_url="https://llm.test/v1",
        model="judge-model",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"choices": []})),
    )

    assert (await timeout_provider.judge(judge_request(policy))).matched_policy_ids == []
    assert (await malformed_provider.judge(judge_request(policy))).matched_policy_ids == []


def test_factory_preserves_legacy_anthropic_config():
    provider = get_judge_provider(
        SimpleNamespace(
            judge_provider=None,
            judge_api_key=None,
            judge_base_url=None,
            judge_model=None,
            anthropic_judge_api_key="legacy-key",
            anthropic_upstream_url="https://anthropic.legacy",
        )
    )

    assert isinstance(provider, AnthropicJudgeProvider)
    assert provider.api_key == "legacy-key"
    assert provider.base_url == "https://anthropic.legacy"


def test_factory_disables_without_credentials_and_unknown_provider():
    missing = get_judge_provider(
        SimpleNamespace(judge_provider="openai", judge_api_key=None, anthropic_judge_api_key=None)
    )
    unknown = get_judge_provider(
        SimpleNamespace(
            judge_provider="nope",
            judge_api_key="test-key",
            anthropic_judge_api_key=None,
        )
    )

    assert isinstance(missing, DisabledJudgeProvider)
    assert missing.is_enabled() is False
    assert isinstance(unknown, DisabledJudgeProvider)
    assert unknown.is_enabled() is False


@pytest.mark.asyncio
async def test_run_nl_texts_uses_provider_and_converts_to_policy_hit(monkeypatch):
    policy = make_policy()

    class FakeProvider:
        provider = "fake"

        def is_enabled(self) -> bool:
            return True

        async def judge(self, req: JudgeRequest) -> JudgeDecision:
            assert req.texts == ["share roadmap"]
            return JudgeDecision([str(policy.id)], "fake", "fake-model")

    monkeypatch.setattr(nl_layer, "get_judge_provider", lambda: FakeProvider())

    hits = await nl_layer.run_nl_texts(["share roadmap"], [policy])

    assert len(hits) == 1
    assert hits[0].policy_id == str(policy.id)
    assert hits[0].layer == PolicyLayer.nl


def test_regex_still_matches_when_judge_is_disabled():
    policy = make_policy(layer=PolicyLayer.regex, pattern=r"SECRET=[A-Za-z0-9]+")

    hits = run_regex_texts(["SECRET=abc"], [policy])

    assert [hit.policy_id for hit in hits] == [str(policy.id)]
