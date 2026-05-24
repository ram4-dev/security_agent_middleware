import logging

import httpx

from app.judge.prompt import (
    JUDGE_MAX_TOKENS,
    JUDGE_TIMEOUT_S,
    build_openai_messages,
    parse_matched_ids,
)
from app.judge.types import JudgeDecision, JudgeRequest

logger = logging.getLogger("app.judge.openai_compatible")

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENCODE_GO_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_OPENCODE_GO_MODEL = "qwen3.6-plus"


class OpenAICompatibleJudgeProvider:
    def __init__(
        self,
        *,
        provider: str,
        api_key: str | None,
        base_url: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.provider = provider
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
            "messages": build_openai_messages(req.policies, req.texts),
            "temperature": 0,
            "max_tokens": JUDGE_MAX_TOKENS,
            "stream": False,
        }
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }

        logger.info(
            "[judge] provider=%s endpoint=/chat/completions model=%s policies=%d",
            self.provider,
            self.model,
            len(req.policies),
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(JUDGE_TIMEOUT_S, connect=3.0),
                transport=self.transport,
            ) as client:
                resp = await client.post("/chat/completions", json=body, headers=headers)
            if resp.status_code != 200:
                logger.warning(
                    "[judge] provider=%s non_200 status=%d",
                    self.provider,
                    resp.status_code,
                )
                return JudgeDecision([], self.provider, self.model)
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[judge] provider=%s error=%s", self.provider, type(exc).__name__)
            return JudgeDecision([], self.provider, self.model)

        content = ""
        try:
            content = payload["choices"][0]["message"].get("content", "")
        except (KeyError, IndexError, TypeError):
            return JudgeDecision([], self.provider, self.model)
        return JudgeDecision(parse_matched_ids(content), self.provider, self.model)
