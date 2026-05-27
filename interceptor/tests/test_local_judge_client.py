import json
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")

import httpx
import pytest
from pydantic import ValidationError

from app.enums import Action, PolicyLayer
from app.local_judge import (
    CandidatePolicy,
    LocalJudgeClient,
    LocalJudgeClientError,
    LocalJudgeDecision,
    LocalJudgeRequest,
    LocalJudgeResponse,
)


def judge_request() -> LocalJudgeRequest:
    return LocalJudgeRequest(
        trace_id="trace-1",
        org_id="demo",
        integration="claude-code",
        wire_api="anthropic_messages",
        model_requested="claude-sonnet-test",
        normalized_request={
            "system": "You are a coding assistant.",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [],
        },
        deterministic_signals=[],
        candidate_policies=[
            CandidatePolicy(
                id="policy-1",
                slug="no-secrets",
                action=Action.REDACT,
                layer=PolicyLayer.nl,
                rule="No secrets",
            )
        ],
    )


@pytest.mark.asyncio
async def test_local_judge_client_posts_contract_and_validates_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "decision": "LOG",
                "confidence": 0.91,
                "risk_type": "BENIGN_REQUEST",
                "severity": "LOW",
                "matched_policy_ids": [],
                "explanation": "The request is benign.",
                "redaction_targets": [],
                "model_version": "qwen3-4b-localjudge-prompt-v1",
            },
        )

    client = LocalJudgeClient(
        base_url="https://local-judge.test/",
        timeout_ms=800,
        transport=httpx.MockTransport(handler),
    )

    response = await client.judge(judge_request())

    assert captured["path"] == "/v1/judge"
    assert captured["body"]["trace_id"] == "trace-1"
    assert captured["body"]["candidate_policies"][0]["action"] == "REDACT"
    assert response.decision == LocalJudgeDecision.LOG
    assert response.risk_type == "BENIGN_REQUEST"


@pytest.mark.asyncio
async def test_local_judge_client_rejects_non_200():
    client = LocalJudgeClient(
        base_url="https://local-judge.test",
        timeout_ms=800,
        transport=httpx.MockTransport(lambda _request: httpx.Response(503, json={})),
    )

    with pytest.raises(LocalJudgeClientError):
        await client.judge(judge_request())


@pytest.mark.asyncio
async def test_local_judge_client_rejects_invalid_json():
    client = LocalJudgeClient(
        base_url="https://local-judge.test",
        timeout_ms=800,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text="not json")),
    )

    with pytest.raises(LocalJudgeClientError):
        await client.judge(judge_request())


@pytest.mark.asyncio
async def test_local_judge_client_rejects_invalid_schema():
    client = LocalJudgeClient(
        base_url="https://local-judge.test",
        timeout_ms=800,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "decision": "REDACT",
                    "confidence": 0.8,
                    "risk_type": "SECRET_LEAK",
                    "severity": "HIGH",
                    "matched_policy_ids": [],
                    "explanation": "Needs redaction.",
                    "redaction_targets": [],
                    "model_version": "qwen3-4b-localjudge-prompt-v1",
                },
            )
        ),
    )

    with pytest.raises(LocalJudgeClientError):
        await client.judge(judge_request())


def test_local_judge_response_requires_redaction_targets_for_redact():
    with pytest.raises(ValidationError):
        LocalJudgeResponse.model_validate(
            {
                "decision": "REDACT",
                "confidence": 0.8,
                "risk_type": "SECRET_LEAK",
                "severity": "HIGH",
                "matched_policy_ids": [],
                "explanation": "Needs redaction.",
                "redaction_targets": [],
                "model_version": "qwen3-4b-localjudge-prompt-v1",
            }
        )


def test_local_judge_response_accepts_valid_redact_target():
    response = LocalJudgeResponse.model_validate(
        {
            "decision": "REDACT",
            "confidence": 0.94,
            "risk_type": "SECRET_LEAK",
            "severity": "HIGH",
            "matched_policy_ids": ["policy-1"],
            "explanation": "The request includes a secret-like value.",
            "redaction_targets": [
                {
                    "path": "$.messages[0].content",
                    "span": {"start": 10, "end": 20},
                    "replacement_type": "secret",
                }
            ],
            "model_version": "qwen3-4b-localjudge-prompt-v1",
        }
    )

    assert response.redaction_targets[0].replacement_type == "SECRET"
