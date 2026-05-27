"""HTTP client for the Specialized Local Judge service."""

from __future__ import annotations

import httpx

from ..config import settings
from .types import LocalJudgeRequest, LocalJudgeResponse


class LocalJudgeClientError(RuntimeError):
    """Raised when the Local Judge boundary cannot provide a trusted decision."""


class LocalJudgeClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_ms: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_ms / 1000)
        self._transport = transport

    async def judge(self, request: LocalJudgeRequest) -> LocalJudgeResponse:
        """Call `/v1/judge` and validate the strict response schema.

        The caller owns fallback decisions. This client only distinguishes a
        trusted, parsed response from a boundary failure.
        """
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    "/v1/judge",
                    json=request.model_dump(mode="json"),
                )
        except httpx.HTTPError as exc:
            raise LocalJudgeClientError("local judge request failed") from exc

        if response.status_code != 200:
            raise LocalJudgeClientError(f"local judge returned HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise LocalJudgeClientError("local judge returned non-JSON response") from exc

        try:
            return LocalJudgeResponse.model_validate(payload)
        except ValueError as exc:
            raise LocalJudgeClientError("local judge response failed validation") from exc


def is_enabled() -> bool:
    return bool(settings.local_judge_enabled and settings.local_judge_base_url)


def get_default_client() -> LocalJudgeClient | None:
    if not is_enabled() or settings.local_judge_base_url is None:
        return None
    return LocalJudgeClient(
        base_url=settings.local_judge_base_url,
        timeout_ms=settings.local_judge_timeout_ms,
    )
