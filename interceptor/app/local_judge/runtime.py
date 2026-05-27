"""Runtime helpers that adapt Local Judge responses to the interceptor cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..cascade import PolicyHit
from ..config import settings
from ..enums import Action, PolicyLayer
from ..models import Policy
from ..protocols import TextPart
from .client import LocalJudgeClient, LocalJudgeClientError, get_default_client
from .types import (
    CandidatePolicy,
    LocalJudgeDecision,
    LocalJudgeRequest,
    LocalJudgeResponse,
    LocalJudgeSeverity,
    NormalizedRequestBody,
    RedactionTarget,
)


@dataclass(frozen=True)
class LocalJudgeEvaluation:
    accepted: bool
    hits: list[PolicyHit]
    fallback_reason: str | None = None
    response: LocalJudgeResponse | None = None


def build_candidate_policies(policies: list[Policy]) -> list[CandidatePolicy]:
    return [
        CandidatePolicy(
            id=str(policy.id),
            slug=policy.slug,
            action=_as_action(policy.default_action),
            layer=_as_layer(policy.layer),
            rule=policy.rule,
            pattern=policy.pattern,
        )
        for policy in policies
    ]


def build_local_judge_request(
    *,
    trace_id: str,
    org_id: str,
    integration: str,
    wire_api: str,
    model_requested: str,
    body_dict: dict[str, Any],
    candidate_policies: list[Policy],
) -> LocalJudgeRequest:
    return LocalJudgeRequest(
        trace_id=trace_id,
        org_id=org_id,
        integration=integration,
        wire_api=wire_api,  # type: ignore[arg-type]
        model_requested=model_requested,
        normalized_request=_normalized_body(wire_api=wire_api, body_dict=body_dict),
        deterministic_signals=[],
        candidate_policies=build_candidate_policies(candidate_policies),
    )


async def evaluate_local_judge(
    *,
    request: LocalJudgeRequest,
    candidate_policies: list[Policy],
    text_parts: list[TextPart],
    client: LocalJudgeClient | None = None,
) -> LocalJudgeEvaluation:
    client = client or get_default_client()
    if client is None:
        return LocalJudgeEvaluation(accepted=False, hits=[], fallback_reason="disabled")

    try:
        response = await client.judge(request)
    except LocalJudgeClientError:
        return LocalJudgeEvaluation(accepted=False, hits=[], fallback_reason="client_error")

    fallback_reason = _fallback_reason(response)
    if fallback_reason is not None:
        return LocalJudgeEvaluation(
            accepted=False,
            hits=[],
            fallback_reason=fallback_reason,
            response=response,
        )

    hits = _response_to_hits(response, candidate_policies, text_parts)
    if hits is None:
        return LocalJudgeEvaluation(
            accepted=False,
            hits=[],
            fallback_reason="invalid_redaction_target",
            response=response,
        )

    return LocalJudgeEvaluation(accepted=True, hits=hits, response=response)


def _normalized_body(*, wire_api: str, body_dict: dict[str, Any]) -> NormalizedRequestBody:
    if wire_api == "anthropic_messages":
        return NormalizedRequestBody(
            system=body_dict.get("system"),
            messages=body_dict.get("messages", []),
            tools=body_dict.get("tools", []),
        )
    if wire_api == "openai_chat":
        return NormalizedRequestBody(
            system=None,
            messages=body_dict.get("messages", []),
            tools=body_dict.get("tools", []),
        )
    return NormalizedRequestBody(messages=[])


def _fallback_reason(response: LocalJudgeResponse) -> str | None:
    if response.decision == LocalJudgeDecision.ESCALATE:
        return "escalate"
    if response.confidence < settings.local_judge_confidence_threshold:
        return "low_confidence"
    if (
        response.severity in {LocalJudgeSeverity.HIGH, LocalJudgeSeverity.CRITICAL}
        and response.confidence < settings.local_judge_high_risk_threshold
    ):
        return "high_risk_low_confidence"
    return None


def _response_to_hits(
    response: LocalJudgeResponse,
    candidate_policies: list[Policy],
    text_parts: list[TextPart],
) -> list[PolicyHit] | None:
    action = _decision_to_action(response.decision)
    if action is None or action == Action.LOG:
        return []

    policies_by_id = {str(policy.id): policy for policy in candidate_policies}
    matched_policy_ids = response.matched_policy_id_set()
    if matched_policy_ids and not matched_policy_ids.issubset(policies_by_id):
        return None

    base_policy = _first_matched_policy(response, policies_by_id)

    if action == Action.REDACT:
        hits: list[PolicyHit] = []
        for target in response.redaction_targets:
            matched_text = _matched_text_for_target(target, text_parts)
            if matched_text is None:
                return None
            hits.append(_hit_from_response(response, action, base_policy, matched_text))
        return hits

    return [_hit_from_response(response, action, base_policy, matched_text="")]


def _decision_to_action(decision: LocalJudgeDecision) -> Action | None:
    if decision == LocalJudgeDecision.ESCALATE:
        return None
    if decision == LocalJudgeDecision.LOG:
        return Action.LOG
    if decision == LocalJudgeDecision.WARN:
        return Action.WARN
    if decision == LocalJudgeDecision.BLOCK:
        return Action.BLOCK
    if decision == LocalJudgeDecision.REDACT:
        return Action.REDACT
    return None


def _first_matched_policy(
    response: LocalJudgeResponse,
    policies_by_id: dict[str, Policy],
) -> Policy | None:
    for policy_id in response.matched_policy_ids:
        policy = policies_by_id.get(policy_id)
        if policy is not None:
            return policy
    return None


def _hit_from_response(
    response: LocalJudgeResponse,
    action: Action,
    policy: Policy | None,
    matched_text: str,
) -> PolicyHit:
    if policy is not None:
        return PolicyHit(
            policy_id=str(policy.id),
            slug=policy.slug,
            layer=_as_layer(policy.layer),
            action=action,
            rule=policy.rule,
            matched_text=matched_text,
        )

    slug = response.risk_type.value.lower().replace("_", "-")
    return PolicyHit(
        policy_id=f"local_judge:{response.risk_type.value}",
        slug=slug,
        layer=PolicyLayer.nl,
        action=action,
        rule=response.explanation,
        matched_text=matched_text,
    )


def _matched_text_for_target(target: RedactionTarget, text_parts: list[TextPart]) -> str | None:
    normalized_target_path = _normalize_path(target.path)
    for part in text_parts:
        if _normalize_path(part.path) != normalized_target_path:
            continue
        if target.span.end > len(part.text):
            return None
        return part.text[target.span.start : target.span.end]
    return None


def _normalize_path(path: str) -> str:
    normalized = path.strip()
    if normalized.startswith("$."):
        normalized = normalized[2:]
    return normalized


def _as_layer(v: object) -> PolicyLayer:
    return v if isinstance(v, PolicyLayer) else PolicyLayer(v)


def _as_action(v: object) -> Action:
    return v if isinstance(v, Action) else Action(v)
