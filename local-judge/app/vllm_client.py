from __future__ import annotations

import httpx

from .config import settings


class VllmClientError(RuntimeError):
    pass


class VllmClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_ms: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = httpx.Timeout(timeout_ms / 1000)
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    async def is_ready(self) -> bool:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.get("/models")
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    async def complete(self, messages: list[dict[str, str]]) -> str:
        body: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "temperature": settings.local_judge_temperature,
            "top_p": settings.local_judge_top_p,
            "max_tokens": settings.local_judge_max_output_tokens,
            "stream": False,
        }
        if settings.local_judge_json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.post("/chat/completions", json=body)
        except httpx.HTTPError as exc:
            raise VllmClientError("vLLM request failed") from exc

        if response.status_code != 200:
            raise VllmClientError(f"vLLM returned HTTP {response.status_code}")

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise VllmClientError("vLLM response shape is invalid") from exc

        if not isinstance(content, str) or not content.strip():
            raise VllmClientError("vLLM returned empty content")
        return content


def get_default_vllm_client() -> VllmClient:
    return VllmClient(
        base_url=settings.local_judge_vllm_base_url,
        model=settings.local_judge_vllm_model,
        timeout_ms=settings.local_judge_request_timeout_ms,
    )
