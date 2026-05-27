"""Protocol-neutral request shapes used by the enforcement cascade."""

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

ProtocolName = Literal["anthropic_messages", "openai_chat", "openai_responses"]


@dataclass(frozen=True)
class TextPart:
    path: str
    role: str | None
    text: str


@dataclass(frozen=True)
class NormalizedRequest:
    protocol: ProtocolName
    integration: str
    org_id: str
    user_id: UUID | None
    trace_id: str
    request_model: str
    stream: bool
    texts: list[TextPart]
    raw_body: dict[str, Any]
    raw_headers: dict[str, str]
    raw_query: str
