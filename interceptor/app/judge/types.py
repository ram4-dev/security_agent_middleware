from dataclasses import dataclass
from typing import Protocol

from app.models import Policy


@dataclass
class JudgeRequest:
    trace_id: str
    org_id: str
    texts: list[str]
    policies: list[Policy]


@dataclass
class JudgeDecision:
    matched_policy_ids: list[str]
    raw_provider: str
    raw_model: str


class JudgeProvider(Protocol):
    provider: str

    def is_enabled(self) -> bool: ...

    async def judge(self, req: JudgeRequest) -> JudgeDecision: ...
