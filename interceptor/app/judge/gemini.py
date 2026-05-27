import logging

import httpx

from app.judge.prompt import (
    JUDGE_MAX_TOKENS,
    JUDGE_TIMEOUT_S,
    build_gemini_prompt,
    parse_matched_ids,
)
from app.judge.types import JudgeDecision, JudgeRequest

logger = logging.getLogger("app.judge.gemini")

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GeminiJudgeProvider:
    provider = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = DEFAULT_GEMINI_BASE_URL,
        model: str = DEFAULT_GEMINI_MODEL,
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
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_gemini_prompt(req.policies, req.texts)}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": JUDGE_MAX_TOKENS,
                "responseMimeType": "application/json",
            },
        }

        logger.info(
            "[judge] provider=gemini endpoint=generateContent model=%s policies=%d",
            self.model,
            len(req.policies),
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(JUDGE_TIMEOUT_S, connect=3.0),
                transport=self.transport,
            ) as client:
                resp = await client.post(
                    f"/models/{self.model}:generateContent",
                    params={"key": self.api_key},
                    json=body,
                )
            if resp.status_code != 200:
                logger.warning("[judge] provider=gemini non_200 status=%d", resp.status_code)
                return JudgeDecision([], self.provider, self.model)
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[judge] provider=gemini error=%s", type(exc).__name__)
            return JudgeDecision([], self.provider, self.model)

        try:
            parts = payload["candidates"][0]["content"].get("parts", [])
        except (KeyError, IndexError, TypeError):
            return JudgeDecision([], self.provider, self.model)
        raw_text = "".join(
            part.get("text", "") for part in parts if isinstance(part, dict) and part.get("text")
        )
        return JudgeDecision(parse_matched_ids(raw_text), self.provider, self.model)
