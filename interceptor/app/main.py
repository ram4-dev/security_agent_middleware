"""Tranquera interceptor — FastAPI entry point.

Endpoints mirror the Anthropic Messages API surface that Claude Code touches:
  - POST /v1/messages              — main proxied call (streaming + non-streaming)
  - POST /v1/messages/count_tokens — passthrough for the CLI's token counter

v0.1 supports the LOG (passthrough) and BLOCK (synthetic 200) paths;
REDACT, WARN, and the pattern/NL layers land in subsequent versions.
"""

import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from ulid import ULID

from .block_response import synthesize_block_message, synthesize_block_sse
from .cascade import PolicyHit, run_regex_layer, run_regex_texts
from .cli_auth import CliCaller, resolve_cli_token
from .config import settings
from .db import get_session
from .enums import Action, PolicyLayer, winning_action
from .models import Interaction, Policy
from .nl_layer import is_enabled as nl_enabled
from .nl_layer import run_nl_layer, run_nl_texts
from .openai_adapter import (
    ChatCompletionsRequest,
    extract_openai_nl_text_parts,
    extract_openai_text_parts,
    flatten_openai_prompt,
    openai_upstream_path,
    redact_openai_chat_body,
    synthesize_openai_block_message,
    synthesize_openai_block_sse,
)
from .redact import redact_for_storage, redact_request_body
from .schemas import MessagesRequest
from .upstream import (
    close_client,
    filtered_response_headers,
    init_client,
    open_openai_compat_upstream,
    open_upstream,
    stream_response,
)

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Forzamos INFO en nuestros módulos para que los pasos de la cascada
    # aparezcan en stdout sin importar la config de uvicorn (en --reload el
    # logger queda en WARNING por default).
    logging.getLogger("app").setLevel(logging.INFO)
    init_client()
    try:
        yield
    finally:
        await close_client()


app = FastAPI(title="Tranquera interceptor", version="0.3.0", lifespan=lifespan)


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


async def _load_active_nl_policies(session: AsyncSession, org_id: str) -> list[Policy]:
    result = await session.exec(
        select(Policy).where(
            Policy.org_id == org_id,
            Policy.is_active.is_(True),  # type: ignore[union-attr]
            Policy.layer == PolicyLayer.nl,
        )
    )
    return list(result.all())


def _winning_hit(hits: list[PolicyHit], action: Action) -> PolicyHit | None:
    return next((h for h in hits if h.action == action), None)


def _diagnostic_headers(*, trace_id: str, action: Action, protocol: str) -> dict[str, str]:
    return {
        "x-tranquera-trace-id": trace_id,
        "x-tranquera-action": action.value,
        "x-tranquera-protocol": protocol,
        # Temporary aliases for older UI/client code during the migration.
        "x-team22-trace-id": trace_id,
        "x-team22-action": action.value,
    }


# Audit column has CHECK (length(prompt) < 50000); leave room for the
# truncation suffix so we never trip the constraint after redaction.
_MAX_STORED_PROMPT_LEN = 49_000


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


def _clip_for_storage(text: str) -> str:
    if len(text) <= _MAX_STORED_PROMPT_LEN:
        return text
    dropped = len(text) - _MAX_STORED_PROMPT_LEN
    return f"{text[:_MAX_STORED_PROMPT_LEN]}\n…[truncated {dropped} chars]"


async def _persist_interaction(
    session: AsyncSession,
    *,
    trace_id: str,
    org_id: str,
    user_id: UUID | None,
    request_model: str,
    hits: list[PolicyHit],
    action: Action,
    reason: str,
    latency_total_ms: int,
    latency_by_layer: dict[str, int],
    upstream_status: int | None,
    parsed: MessagesRequest | None = None,
    prompt: str | None = None,
    protocol: str = "anthropic_messages",
    integration: str = "claude-code",
    upstream_provider: str | None = None,
    upstream_model: str | None = None,
) -> None:
    if prompt is None:
        prompt = "" if parsed is None else _flatten_prompt(parsed)
    interaction = Interaction(
        trace_id=trace_id,
        org_id=org_id,
        user_id=user_id,
        request_model=request_model,
        protocol=protocol,
        integration=integration,
        upstream_provider=upstream_provider,
        upstream_model=upstream_model,
        prompt=_clip_for_storage(redact_for_storage(prompt, hits)),
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
async def messages_unauthorized():
    # The unattributed route is closed: every legitimate caller goes through
    # /cli/{token}/v1/messages thanks to `tranquera setup`. Anyone hitting
    # this path is misconfigured (or probing) — fail loud instead of writing
    # orphan rows under the default org.
    return JSONResponse(
        {
            "error": "missing tranquera token",
            "hint": "run `npx tranquera setup` so ANTHROPIC_BASE_URL points to /cli/<token>",
        },
        status_code=401,
    )


@app.post("/cli/{token}/v1/messages")
async def messages_via_cli(
    token: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Same as /v1/messages but identifies the caller from the URL path.

    Claude Code doesn't let us inject custom headers, but it does respect the
    full path of `ANTHROPIC_BASE_URL`. The CLI bakes the token in there so
    every prompt becomes attributable to the dev who ran `tranquera setup`.
    """
    caller = await resolve_cli_token(session, token)
    if caller is None:
        return JSONResponse(
            {"error": "unknown or revoked tranquera token"},
            status_code=401,
        )
    return await _process_messages(request, session, caller=caller)


@app.post("/openai/cli/{token}/v1/chat/completions")
async def openai_chat_via_cli(
    token: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    caller = await resolve_cli_token(session, token)
    if caller is None:
        return JSONResponse(
            {"error": "unknown or revoked tranquera token"},
            status_code=401,
        )
    return await _process_openai_chat(request, session, caller=caller)


async def _process_openai_chat(
    request: Request,
    session: AsyncSession,
    *,
    caller: CliCaller,
):
    started = time.perf_counter()
    raw_body = await request.body()

    try:
        body_dict: dict[str, Any] = json.loads(raw_body)
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    try:
        parsed = ChatCompletionsRequest.model_validate(body_dict)
    except ValidationError as exc:
        return JSONResponse(
            {"error": "invalid chat completions api shape", "detail": exc.errors()},
            status_code=400,
        )

    trace_id = str(ULID())
    org_id = caller.org_id
    user_id: UUID | None = caller.member_id
    is_streaming = bool(parsed.stream)

    logger.info(
        "[openai-req] trace=%s org=%s user=%s model=%s stream=%s provider=%s",
        trace_id,
        org_id,
        str(user_id) if user_id else "-",
        parsed.model,
        is_streaming,
        settings.openai_compat_provider,
    )

    regex_started = time.perf_counter()
    regex_policies = await _load_active_regex_policies(session, org_id)
    text_parts = extract_openai_text_parts(parsed)
    hits = run_regex_texts([part.text for part in text_parts], regex_policies)
    regex_ms = int((time.perf_counter() - regex_started) * 1000)
    latency_by_layer: dict[str, int] = {"regex": regex_ms}

    action = winning_action([h.action for h in hits])
    logger.info(
        "[openai-regex] trace=%s policies=%d hits=%d action=%s elapsed=%dms",
        trace_id,
        len(regex_policies),
        len(hits),
        action.value,
        regex_ms,
    )

    # Reuse the same post-regex NL cascade semantics as the Anthropic route,
    # but feed the judge protocol-normalized OpenAI text instead of an
    # Anthropic MessagesRequest schema.
    if action == Action.BLOCK:
        logger.info("[openai-nl] trace=%s skipped reason=regex_blocked", trace_id)
    elif not nl_enabled():
        logger.info("[openai-nl] trace=%s skipped reason=no_judge_api_key", trace_id)
    else:
        nl_policies = await _load_active_nl_policies(session, org_id)
        if not nl_policies:
            logger.info("[openai-nl] trace=%s skipped reason=no_active_nl_policies", trace_id)
        else:
            logger.info(
                "[openai-nl] trace=%s calling judge policies=%d",
                trace_id,
                len(nl_policies),
            )
            nl_started = time.perf_counter()
            nl_text_parts = extract_openai_nl_text_parts(parsed)
            nl_hits = await run_nl_texts([part.text for part in nl_text_parts], nl_policies)
            nl_ms = int((time.perf_counter() - nl_started) * 1000)
            latency_by_layer["nl"] = nl_ms
            logger.info(
                "[openai-nl] trace=%s hits=%d elapsed=%dms slugs=%s",
                trace_id,
                len(nl_hits),
                nl_ms,
                [h.slug for h in nl_hits],
            )
            if nl_hits:
                hits = hits + nl_hits
                action = winning_action([h.action for h in hits])

    response_headers = _diagnostic_headers(
        trace_id=trace_id,
        action=action,
        protocol="openai_chat",
    )

    if action == Action.BLOCK:
        hit = _winning_hit(hits, Action.BLOCK)
        assert hit is not None
        reason = f"matchea regla {hit.slug}: {hit.rule}"
        await _persist_interaction(
            session,
            trace_id=trace_id,
            org_id=org_id,
            user_id=user_id,
            request_model=parsed.model,
            prompt=flatten_openai_prompt(parsed),
            hits=hits,
            action=action,
            reason=reason,
            latency_total_ms=int((time.perf_counter() - started) * 1000),
            latency_by_layer=latency_by_layer,
            upstream_status=None,
            protocol="openai_chat",
            integration=settings.openai_compat_integration,
            upstream_provider=settings.openai_compat_provider,
            upstream_model=parsed.model,
        )
        if is_streaming:
            return StreamingResponse(
                synthesize_openai_block_sse(parsed.model, trace_id, hit),
                status_code=200,
                headers=response_headers,
                media_type="text/event-stream",
            )
        return JSONResponse(
            content=synthesize_openai_block_message(parsed.model, trace_id, hit),
            status_code=200,
            headers=response_headers,
        )

    outbound_body = raw_body
    reason = "no policy matched"
    if action == Action.REDACT:
        redact_hits = [h for h in hits if h.action == Action.REDACT]
        slugs = ", ".join(sorted({h.slug for h in redact_hits}))
        reason = f"datos sensibles enmascarados por regla {slugs}"
        redacted_body_dict, skipped_non_text = redact_openai_chat_body(body_dict, redact_hits)
        if skipped_non_text:
            latency_by_layer["redaction_skipped_non_text_blocks"] = 1
        outbound_body = json.dumps(redacted_body_dict).encode()
    elif hits:
        slugs = ", ".join(sorted({h.slug for h in hits}))
        reason = f"matchearon reglas: {slugs}"

    upstream_started = time.perf_counter()
    upstream_resp = await open_openai_compat_upstream(
        "POST",
        openai_upstream_path(settings.openai_compat_upstream_url),
        outbound_body,
        dict(request.headers),
        request.url.query,
    )
    latency_by_layer["upstream_open_ms"] = int(
        (time.perf_counter() - upstream_started) * 1000
    )

    await _persist_interaction(
        session,
        trace_id=trace_id,
        org_id=org_id,
        user_id=user_id,
        request_model=parsed.model,
        prompt=flatten_openai_prompt(parsed),
        hits=hits,
        action=action,
        reason=reason,
        latency_total_ms=int((time.perf_counter() - started) * 1000),
        latency_by_layer=latency_by_layer,
        upstream_status=upstream_resp.status_code,
        protocol="openai_chat",
        integration=settings.openai_compat_integration,
        upstream_provider=settings.openai_compat_provider,
        upstream_model=parsed.model,
    )

    upstream_headers = filtered_response_headers(upstream_resp.headers)
    upstream_headers.update(response_headers)
    return StreamingResponse(
        stream_response(upstream_resp),
        status_code=upstream_resp.status_code,
        headers=upstream_headers,
        media_type=upstream_resp.headers.get("content-type"),
    )


async def _process_messages(
    request: Request,
    session: AsyncSession,
    *,
    caller: CliCaller | None,
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
    if caller is not None:
        org_id = caller.org_id
        user_id: UUID | None = caller.member_id
    else:
        org_id = request.headers.get("x-team22-org-key", settings.default_org_id)
        user_id = None
    trace_id = str(ULID())

    logger.info(
        "[req] trace=%s org=%s user=%s model=%s stream=%s",
        trace_id, org_id, str(user_id) if user_id else "-",
        parsed.model, is_streaming,
    )

    # ----- Layer 1: regex -----------------------------------------
    regex_started = time.perf_counter()
    regex_policies = await _load_active_regex_policies(session, org_id)
    hits = run_regex_layer(parsed, regex_policies)
    regex_ms = int((time.perf_counter() - regex_started) * 1000)
    latency_by_layer: dict[str, int] = {"regex": regex_ms}

    action = winning_action([h.action for h in hits])
    logger.info(
        "[regex] trace=%s policies=%d hits=%d action=%s elapsed=%dms",
        trace_id, len(regex_policies), len(hits), action.value, regex_ms,
    )

    # ----- Layer 3: NL judge --------------------------------------
    # Saltamos si regex ya BLOQUEÓ (no hay nada que sumar) o si el judge
    # no tiene API key configurada (fail open, comportamiento v0.1).
    if action == Action.BLOCK:
        logger.info("[nl] trace=%s skipped reason=regex_blocked", trace_id)
    elif not nl_enabled():
        logger.info("[nl] trace=%s skipped reason=no_judge_api_key", trace_id)
    else:
        nl_policies = await _load_active_nl_policies(session, org_id)
        if not nl_policies:
            logger.info("[nl] trace=%s skipped reason=no_active_nl_policies", trace_id)
        else:
            logger.info(
                "[nl] trace=%s calling judge policies=%d",
                trace_id, len(nl_policies),
            )
            nl_started = time.perf_counter()
            nl_hits = await run_nl_layer(parsed, nl_policies)
            nl_ms = int((time.perf_counter() - nl_started) * 1000)
            latency_by_layer["nl"] = nl_ms
            logger.info(
                "[nl] trace=%s hits=%d elapsed=%dms slugs=%s",
                trace_id, len(nl_hits), nl_ms, [h.slug for h in nl_hits],
            )
            if nl_hits:
                hits = hits + nl_hits
                action = winning_action([h.action for h in hits])

    response_headers = _diagnostic_headers(
        trace_id=trace_id,
        action=action,
        protocol="anthropic_messages",
    )

    # ----- BLOCK --------------------------------------------------
    if action == Action.BLOCK:
        hit = _winning_hit(hits, Action.BLOCK)
        assert hit is not None
        reason = f"matchea regla {hit.slug}: {hit.rule}"
        logger.info(
            "[done] trace=%s action=BLOCK by=%s/%s",
            trace_id, hit.layer.value, hit.slug,
        )
        await _persist_interaction(
            session,
            trace_id=trace_id,
            org_id=org_id,
            user_id=user_id,
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

    # ----- REDACT -------------------------------------------------
    # Secrets are masked inline; the mutated request reaches the upstream
    # so the dev can keep working — the sensitive value never leaves.
    if action == Action.REDACT:
        redact_hits = [h for h in hits if h.action == Action.REDACT]
        slugs = ", ".join(sorted({h.slug for h in redact_hits}))
        reason = f"datos sensibles enmascarados por regla {slugs}"
        logger.info(
            "[done] trace=%s action=REDACT slugs=%s",
            trace_id, slugs,
        )
        redacted_body_dict = redact_request_body(body_dict, redact_hits)
        redacted_raw = json.dumps(redacted_body_dict).encode()

        upstream_started = time.perf_counter()
        upstream_resp = await open_upstream(
            "POST",
            "/v1/messages",
            redacted_raw,
            dict(request.headers),
            request.url.query,
        )
        latency_by_layer["upstream_open_ms"] = int(
            (time.perf_counter() - upstream_started) * 1000
        )

        await _persist_interaction(
            session,
            trace_id=trace_id,
            org_id=org_id,
            user_id=user_id,
            request_model=parsed.model,
            parsed=parsed,
            hits=hits,
            action=action,
            reason=reason,
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

    # ----- LOG / WARN (passthrough, original body) ----------------
    upstream_started = time.perf_counter()
    upstream_resp = await open_upstream(
        "POST",
        "/v1/messages",
        raw_body,
        dict(request.headers),
        request.url.query,
    )
    latency_by_layer["upstream_open_ms"] = int(
        (time.perf_counter() - upstream_started) * 1000
    )

    if hits:
        slugs = ", ".join(sorted({h.slug for h in hits}))
        reason = f"matchearon reglas: {slugs}"
    else:
        reason = "no policy matched"

    logger.info(
        "[done] trace=%s action=%s upstream_status=%d total=%dms",
        trace_id, action.value, upstream_resp.status_code,
        int((time.perf_counter() - started) * 1000),
    )

    # Persist before piping the body — we don't read the response body, only
    # relay it. Audit row is written based on the upstream status header.
    await _persist_interaction(
        session,
        trace_id=trace_id,
        org_id=org_id,
        user_id=user_id,
        request_model=parsed.model,
        parsed=parsed,
        hits=hits,
        action=action,
        reason=reason,
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
    return await _passthrough_count_tokens(request)


@app.post("/cli/{token}/v1/messages/count_tokens")
async def count_tokens_via_cli(token: str, request: Request):
    # We don't gate count_tokens on token validity — it's a read-only helper
    # Claude Code calls before every prompt, and rejecting it would make the
    # whole CLI unusable on revoked/expired tokens. The actual /v1/messages
    # call enforces auth.
    return await _passthrough_count_tokens(request)


async def _passthrough_count_tokens(request: Request):
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
