import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.parser import ModelOutputError, parse_model_output
from app.prompt import build_messages
from app.schemas import LocalJudgeRequest
from app.vllm_client import VllmClient


class FakeVllmClient:
    def __init__(self, *, ready=True, output=None):
        self.ready = ready
        self.output = output or json.dumps(
            {
                "decision": "LOG",
                "confidence": 0.92,
                "risk_type": "BENIGN_REQUEST",
                "severity": "LOW",
                "matched_policy_ids": [],
                "explanation": "The request is benign.",
                "redaction_targets": [],
            }
        )
        self.messages = None

    async def is_ready(self):
        return self.ready

    async def complete(self, messages):
        self.messages = messages
        return self.output


def judge_payload():
    return {
        "trace_id": "trace-1",
        "org_id": "demo",
        "integration": "claude-code",
        "wire_api": "anthropic_messages",
        "model_requested": "claude-sonnet-test",
        "normalized_request": {
            "system": "You are a coding assistant.",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [],
        },
        "deterministic_signals": [],
        "candidate_policies": [],
    }


@pytest.fixture(autouse=True)
def clear_overrides():
    main.app.dependency_overrides.clear()
    yield
    main.app.dependency_overrides.clear()


def test_healthz_and_metadata():
    client = TestClient(main.app)

    assert client.get("/healthz").json() == {"status": "ok"}
    metadata = client.get("/v1/metadata").json()

    assert metadata["service"] == "tranquera-local-judge"
    assert metadata["prompt_version"] == "local_judge_v1"
    assert metadata["risk_taxonomy_version"] == "risk_taxonomy_v1"


def test_readyz_uses_model_readiness():
    main.app.dependency_overrides[main.get_vllm_client] = lambda: FakeVllmClient(ready=True)
    client = TestClient(main.app)

    assert client.get("/readyz").status_code == 200
    assert client.get("/readyz").json() == {"status": "ready"}


def test_readyz_returns_503_when_model_unavailable():
    main.app.dependency_overrides[main.get_vllm_client] = lambda: FakeVllmClient(ready=False)
    client = TestClient(main.app)

    resp = client.get("/readyz")

    assert resp.status_code == 503
    assert resp.json() == {"status": "not_ready"}


def test_judge_calls_model_and_returns_validated_json():
    fake = FakeVllmClient()
    main.app.dependency_overrides[main.get_vllm_client] = lambda: fake
    client = TestClient(main.app)

    resp = client.post("/v1/judge", json=judge_payload())

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "LOG"
    assert body["model_version"] == "Qwen/Qwen3-4B-Instruct-2507:local_judge_v1"
    assert fake.messages[0]["role"] == "system"
    assert fake.messages[1]["role"] == "user"


def test_judge_returns_422_for_invalid_request_shape():
    client = TestClient(main.app)

    resp = client.post("/v1/judge", json={"trace_id": "trace-1"})

    assert resp.status_code == 422


def test_judge_returns_503_for_invalid_model_output():
    main.app.dependency_overrides[main.get_vllm_client] = lambda: FakeVllmClient(output="not json")
    client = TestClient(main.app)

    resp = client.post("/v1/judge", json=judge_payload())

    assert resp.status_code == 503
    assert resp.json() == {"error": "invalid_model_output", "trace_id": "trace-1"}


def test_parse_model_output_rejects_secretish_explanation():
    with pytest.raises(ModelOutputError):
        parse_model_output(
            json.dumps(
                {
                    "decision": "BLOCK",
                    "confidence": 0.99,
                    "risk_type": "SECRET_LEAK",
                    "severity": "HIGH",
                    "matched_policy_ids": [],
                    "explanation": "The value API_KEY=sk-abc123456789000 should not be sent.",
                    "redaction_targets": [],
                    "model_version": "test",
                }
            ),
            default_model_version="test",
        )


def test_build_messages_serializes_request():
    request = LocalJudgeRequest.model_validate(judge_payload())

    messages = build_messages(request)

    assert messages[0]["role"] == "system"
    assert "Tranquera Local Judge" in messages[0]["content"]
    assert json.loads(messages[1]["content"])["trace_id"] == "trace-1"


@pytest.mark.asyncio
async def test_vllm_client_posts_chat_completion_contract():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "decision": "LOG",
                                    "confidence": 0.9,
                                    "risk_type": "BENIGN_REQUEST",
                                    "severity": "LOW",
                                    "matched_policy_ids": [],
                                    "explanation": "The request is benign.",
                                    "redaction_targets": [],
                                    "model_version": "test",
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = VllmClient(
        base_url="https://vllm.test/v1",
        model="judge-model",
        timeout_ms=700,
        transport=httpx.MockTransport(handler),
    )

    content = await client.complete([{"role": "user", "content": "hi"}])

    assert captured["path"] == "/v1/chat/completions"
    assert captured["body"]["model"] == "judge-model"
    assert captured["body"]["stream"] is False
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert json.loads(content)["decision"] == "LOG"
