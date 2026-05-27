import logging

import httpx

from app.judge.prompt import (
    JUDGE_MAX_TOKENS,
    JUDGE_SYSTEM,
    JUDGE_TIMEOUT_S,
    build_anthropic_messages,
    parse_matched_ids,
)
from app.judge.types import JudgeDecision, JudgeRequest

logger = logging.getLogger("app.judge.anthropic")

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"


class AnthropicJudgeProvider:
    provider = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = DEFAULT_ANTHROPIC_BASE_URL,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    async def judge(self, req: JudgeRequest) -> JudgeDecision:
        if not self.api_key:
            return JudgeDecision([], self.provider, self.model)

        body = {
            "model": self.model,
            "max_tokens": JUDGE_MAX_TOKENS,
            "system": JUDGE_SYSTEM,
            "messages": build_anthropic_messages(req.policies, req.texts),
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        logger.info(
            "[judge] provider=anthropic endpoint=/v1/messages model=%s policies=%d",
            self.model,
            len(req.policies),
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(JUDGE_TIMEOUT_S, connect=3.0),
                transport=self.transport,
            ) as client:
                resp = await client.post("/v1/messages", json=body, headers=headers)
            if resp.status_code != 200:
                logger.warning("[judge] provider=anthropic non_200 status=%d", resp.status_code)
                return JudgeDecision([], self.provider, self.model)
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[judge] provider=anthropic error=%s", type(exc).__name__)
            return JudgeDecision([], self.provider, self.model)

        text_chunks = [
            block.get("text", "")
            for block in payload.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return JudgeDecision(parse_matched_ids("".join(text_chunks)), self.provider, self.model)
