"""Strict contracts for the Specialized Local Judge service.

These shapes mirror spec 17 and intentionally stay independent from the
service implementation in spec 18. The interceptor uses them to validate the
HTTP boundary before trusting any local model decision.
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..enums import Action, PolicyLayer


class LocalJudgeDecision(StrEnum):
    LOG = "LOG"
    WARN = "WARN"
    BLOCK = "BLOCK"
    REDACT = "REDACT"
    ESCALATE = "ESCALATE"


class RiskType(StrEnum):
    SECRET_LEAK = "SECRET_LEAK"
    PII_LEAK = "PII_LEAK"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    POLICY_BYPASS = "POLICY_BYPASS"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    DESTRUCTIVE_ACTION = "DESTRUCTIVE_ACTION"
    UNSAFE_TOOL_USE = "UNSAFE_TOOL_USE"
    CREDENTIAL_ABUSE = "CREDENTIAL_ABUSE"
    PRIVATE_CODE_LEAK = "PRIVATE_CODE_LEAK"
    BENIGN_REQUEST = "BENIGN_REQUEST"


class LocalJudgeSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Span(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "Span":
        if self.end <= self.start:
            raise ValueError("span.end must be greater than span.start")
        return self


class DeterministicSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1)
    path: str = Field(min_length=1)
    span: Span | None = None
    confidence: float = Field(ge=0, le=1)


class CandidatePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    action: Action
    layer: PolicyLayer
    rule: str = Field(min_length=1)
    pattern: str | None = None


class NormalizedMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str = Field(min_length=1)
    content: str | list[dict[str, Any]] | None = None


class NormalizedRequestBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    system: str | list[dict[str, Any]] | None = None
    messages: list[NormalizedMessage] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)


class LocalJudgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(min_length=1)
    org_id: str = Field(min_length=1)
    integration: str = Field(min_length=1)
    wire_api: Literal["anthropic_messages", "openai_chat", "openai_responses"]
    model_requested: str = Field(min_length=1)
    normalized_request: NormalizedRequestBody
    deterministic_signals: list[DeterministicSignal] = Field(default_factory=list)
    candidate_policies: list[CandidatePolicy] = Field(default_factory=list)


class RedactionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    span: Span
    replacement_type: str = Field(min_length=1)

    @field_validator("replacement_type")
    @classmethod
    def normalize_replacement_type(cls, value: str) -> str:
        return value.strip().upper()


class LocalJudgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: LocalJudgeDecision
    confidence: float = Field(ge=0, le=1)
    risk_type: RiskType
    severity: LocalJudgeSeverity
    matched_policy_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1, max_length=500)
    redaction_targets: list[RedactionTarget] = Field(default_factory=list)
    model_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_decision_payload(self) -> "LocalJudgeResponse":
        if self.decision == LocalJudgeDecision.REDACT and not self.redaction_targets:
            raise ValueError("REDACT decisions must include at least one redaction target")
        if self.decision != LocalJudgeDecision.REDACT and self.redaction_targets:
            raise ValueError("redaction targets are only valid for REDACT decisions")
        return self

    def matched_policy_id_set(self) -> set[str]:
        return set(self.matched_policy_ids)
