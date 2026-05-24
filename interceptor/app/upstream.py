"""HTTP client to forward requests to api.anthropic.com.

We always open the upstream call as a stream and pipe raw bytes back to
the caller. This makes both streaming (SSE) and non-streaming (JSON)
responses Just Work — we never re-parse the body, so we can't corrupt it.

A single shared httpx.AsyncClient is created at app startup so connection
pooling pays off.
"""

from collections.abc import AsyncIterator
from urllib.parse import urlparse, urlunparse

import httpx

from .config import settings

_client: httpx.AsyncClient | None = None
_openai_client: httpx.AsyncClient | None = None

# Hop-by-hop and content-length headers we must NOT relay back to the caller —
# httpx already decoded the body and Starlette will set its own length.
_FORBIDDEN_RESPONSE_HEADERS = {
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive",
}

# Headers we drop from inbound before forwarding upstream.
_FORBIDDEN_REQUEST_HEADERS = {
    "host",
    "content-length",
    "connection",
    "transfer-encoding",
}


def _strip_trailing_v1(base_url: str) -> str:
    parsed = urlparse(base_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3] or ""
    return urlunparse(parsed._replace(path=path or "", params="", query="", fragment=""))


def init_client() -> None:
    global _client, _openai_client
    _client = httpx.AsyncClient(
        base_url=settings.anthropic_upstream_url,
        timeout=httpx.Timeout(120.0, connect=5.0),
    )
    _openai_client = httpx.AsyncClient(
        base_url=_strip_trailing_v1(settings.openai_compat_upstream_url),
        timeout=httpx.Timeout(120.0, connect=5.0),
    )


async def close_client() -> None:
    global _client, _openai_client
    if _client is not None:
        await _client.aclose()
        _client = None
    if _openai_client is not None:
        await _openai_client.aclose()
        _openai_client = None


def filtered_request_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _FORBIDDEN_REQUEST_HEADERS}


def filtered_response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _FORBIDDEN_RESPONSE_HEADERS}


async def _open_with_client(
    client: httpx.AsyncClient | None,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    query_string: str = "",
) -> httpx.Response:
    if client is None:
        raise RuntimeError("upstream client not initialised")

    full_path = f"{path}?{query_string}" if query_string else path
    request = client.build_request(
        method,
        full_path,
        content=body,
        headers=filtered_request_headers(headers),
    )
    return await client.send(request, stream=True)


async def open_upstream(
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    query_string: str = "",
) -> httpx.Response:
    """Open a streamed Anthropic upstream call. Returns the open Response — the caller
    is responsible for iterating its body and closing it via `aclose()`."""
    return await _open_with_client(_client, method, path, body, headers, query_string)


async def open_openai_compat_upstream(
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    query_string: str = "",
) -> httpx.Response:
    """Open a streamed OpenAI-compatible upstream call."""
    return await _open_with_client(_openai_client, method, path, body, headers, query_string)


async def stream_response(response: httpx.Response) -> AsyncIterator[bytes]:
    """Pipe upstream bytes through, decompressed, then close the connection.

    `aiter_bytes()` (not `aiter_raw()`) is critical: Anthropic frequently
    gzip-encodes JSON responses and `aiter_raw()` would forward the
    compressed bytes while we strip `content-encoding` from the headers,
    leaving the client unable to decode them.
    """
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    finally:
        await response.aclose()
