"""Tranquera interceptor — FastAPI entry point.

Endpoints mirror the Anthropic Messages API surface that Claude Code touches:
  - POST /v1/messages              — main proxied call (streaming + non-streaming)
  - POST /v1/messages/count_tokens — passthrough for the CLI's token counter

v0.1 supports the LOG (passthrough) and BLOCK (synthetic 200) paths;
REDACT, WARN, and the pattern/NL layers land in subsequent versions.
"""

import json
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from ulid import ULID

from .block_response import synthesize_block_message, synthesize_block_sse
from .cascade import PolicyHit, run_regex_layer
from .config import settings
from .db import get_session
from .enums import Action, PolicyLayer, winning_action
from .models import Interaction, Policy
from .redact import redact_for_storage
from .schemas import MessagesRequest
from .upstream import (
    close_client,
    filtered_response_headers,
    init_client,
    open_upstream,
    stream_response,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_client()
    try:
        yield
    finally:
        await close_client()


app = FastAPI(title="Tranquera interceptor", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_active_regex_policies(session: AsyncSession, org_id: str) -> list[Policy]:
    result = await session.exec(
        select(Policy).where(
            Policy.org_id == org_id,
            Policy.is_active.is_(True),  # type: ignore[union-attr]
            Policy.layer == PolicyLayer.regex,
        )
    )
    return list(result.all())


def _winning_hit(hits: list[PolicyHit], action: Action) -> PolicyHit | None:
    return next((h for h in hits if h.action == action), None)


def _flatten_prompt(req: MessagesRequest) -> str:
    """Concat all text blocks for storage. Redaction runs after this."""
    chunks: list[str] = []
    if isinstance(req.system, str):
        chunks.append(f"[system] {req.system}")
    for msg in req.messages:
        if isinstance(msg.content, str):
            chunks.append(f"[{msg.role}] {msg.content}")
        else:
            for b in msg.content:
                if b.get("type") == "text":
                    chunks.append(f"[{msg.role}] {b.get('text', '')}")
    return "\n".join(chunks)


async def _persist_interaction(
    session: AsyncSession,
    *,
    trace_id: str,
    org_id: str,
    request_model: str,
    parsed: MessagesRequest,
    hits: list[PolicyHit],
    action: Action,
    reason: str,
    latency_total_ms: int,
    latency_by_layer: dict[str, int],
    upstream_status: int | None,
) -> None:
    interaction = Interaction(
        trace_id=trace_id,
        org_id=org_id,
        request_model=request_model,
        prompt=redact_for_storage(_flatten_prompt(parsed), hits),
        action=action,
        reason=reason,
        policy_hits=[h.to_record() for h in hits],
        latency_total_ms=latency_total_ms,
        latency_by_layer=latency_by_layer,
        upstream_status=upstream_status,
    )
    session.add(interaction)
    await session.commit()


# ---------------------------------------------------------------------------
# /v1/messages — the cascade lives here.
# ---------------------------------------------------------------------------


@app.post("/v1/messages")
async def messages(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    started = time.perf_counter()
    raw_body = await request.body()

    try:
        body_dict: dict[str, Any] = json.loads(raw_body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    try:
        parsed = MessagesRequest.model_validate(body_dict)
    except ValidationError as exc:
        return JSONResponse(
            {"error": "invalid messages api shape", "detail": exc.errors()},
            status_code=400,
        )

    is_streaming = bool(body_dict.get("stream"))
    org_id = request.headers.get("x-team22-org-key", settings.default_org_id)
    trace_id = str(ULID())

    # ----- Layer 1: regex -----------------------------------------
    regex_started = time.perf_counter()
    policies = await _load_active_regex_policies(session, org_id)
    hits = run_regex_layer(parsed, policies)
    regex_ms = int((time.perf_counter() - regex_started) * 1000)
    latency_by_layer: dict[str, int] = {"regex": regex_ms}

    action = winning_action([h.action for h in hits])
    response_headers = {
        "x-team22-trace-id": trace_id,
        "x-team22-action": action.value,
    }

    # ----- BLOCK --------------------------------------------------
    if action == Action.BLOCK:
        hit = _winning_hit(hits, Action.BLOCK)
        assert hit is not None
        reason = f"matchea regla {hit.slug}: {hit.rule}"
        await _persist_interaction(
            session,
            trace_id=trace_id,
            org_id=org_id,
            request_model=parsed.model,
            parsed=parsed,
            hits=hits,
            action=action,
            reason=reason,
            latency_total_ms=int((time.perf_counter() - started) * 1000),
            latency_by_layer=latency_by_layer,
            upstream_status=None,
        )
        if is_streaming:
            return StreamingResponse(
                synthesize_block_sse(parsed.model, trace_id, hit),
                status_code=200,
                headers=response_headers,
                media_type="text/event-stream",
            )
        return JSONResponse(
            content=synthesize_block_message(parsed.model, trace_id, hit),
            status_code=200,
            headers=response_headers,
        )

    # ----- LOG (passthrough) --------------------------------------
    upstream_resp = await open_upstream(
        "POST",
        "/v1/messages",
        raw_body,
        dict(request.headers),
        request.url.query,
    )
    latency_by_layer["upstream_open_ms"] = (
        int((time.perf_counter() - started) * 1000) - regex_ms
    )

    # Persist before piping the body — we don't read the response body, only
    # relay it. Audit row is written based on the upstream status header.
    await _persist_interaction(
        session,
        trace_id=trace_id,
        org_id=org_id,
        request_model=parsed.model,
        parsed=parsed,
        hits=hits,
        action=action,
        reason="no policy matched" if not hits else "logged for audit",
        latency_total_ms=int((time.perf_counter() - started) * 1000),
        latency_by_layer=latency_by_layer,
        upstream_status=upstream_resp.status_code,
    )

    upstream_headers = filtered_response_headers(upstream_resp.headers)
    upstream_headers.update(response_headers)

    return StreamingResponse(
        stream_response(upstream_resp),
        status_code=upstream_resp.status_code,
        headers=upstream_headers,
        media_type=upstream_resp.headers.get("content-type"),
    )


# ---------------------------------------------------------------------------
# /v1/messages/count_tokens — passthrough, no cascade.
# ---------------------------------------------------------------------------


@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    raw_body = await request.body()
    upstream_resp = await open_upstream(
        "POST",
        "/v1/messages/count_tokens",
        raw_body,
        dict(request.headers),
        request.url.query,
    )
    body = await upstream_resp.aread()
    await upstream_resp.aclose()
    return Response(
        content=body,
        status_code=upstream_resp.status_code,
        headers=filtered_response_headers(upstream_resp.headers),
        media_type=upstream_resp.headers.get("content-type"),
    )
