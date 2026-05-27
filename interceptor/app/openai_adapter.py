"""OpenAI Chat Completions protocol adapter.

The adapter intentionally accepts a permissive subset of Chat Completions:
we validate the fields Tranquera needs for policy enforcement, preserve extra
provider/client fields, and forward the request body without translating tool
or non-text content.
"""

from __future__ import annotations

import copy
import json
import re
import time
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .cascade import PolicyHit
from .protocols import TextPart

OPENAI_CHAT_PROTOCOL = "openai_chat"
OPENAI_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
EVALUABLE_OPENAI_ROLES = {"system", "developer", "user"}
NL_EVALUABLE_OPENAI_ROLES = {"developer", "user"}


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "developer", "user", "assistant", "tool"] | str
    content: str | list[dict[str, Any]] | None = None


class ChatCompletionsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[ChatMessage]
    stream: bool = False


def extract_openai_text_parts(req: ChatCompletionsRequest) -> list[TextPart]:
    """Extract only policy-evaluable Chat Completions text.

    Assistant and tool messages are intentionally skipped for this phase; they
    may contain local tool output or prior model output that we do not rewrite
    in the v1 adapter.
    """
    parts: list[TextPart] = []
    for msg_index, msg in enumerate(req.messages):
        role = str(msg.role)
        if role not in EVALUABLE_OPENAI_ROLES:
            continue
        content = msg.content
        if isinstance(content, str):
            if content:
                parts.append(TextPart(f"messages[{msg_index}].content", role, content))
            continue
        if isinstance(content, list):
            for block_index, block in enumerate(content):
                if not isinstance(block, dict) or block.get("type") != "text":
                    continue
                text = block.get("text")
                if isinstance(text, str) and text:
                    parts.append(
                        TextPart(
                            f"messages[{msg_index}].content[{block_index}].text",
                            role,
                            text,
                        )
                    )
    return parts


def extract_openai_nl_text_parts(req: ChatCompletionsRequest) -> list[TextPart]:
    """Extract text sent to the expensive NL judge.

    Regex still scans system/developer/user text. The NL judge skips system
    prompts because CLI harnesses can inject huge static instructions there,
    which dilutes the actual user prompt and can make provider calls timeout.
    """
    return [
        part for part in extract_openai_text_parts(req) if part.role in NL_EVALUABLE_OPENAI_ROLES
    ]


def flatten_openai_prompt(req: ChatCompletionsRequest) -> str:
    return "\n".join(f"[{part.role}] {part.text}" for part in extract_openai_text_parts(req))


def _block_text(hit: PolicyHit) -> str:
    return (
        f"Tu prompt se cruzó con la política `{hit.slug}`: {hit.rule}. "
        "Reformulalo sin incluir ese dato o coordiná con tu admin. — Tranquera"
    )


def synthesize_openai_block_message(model: str, trace_id: str, hit: PolicyHit) -> dict[str, Any]:
    return {
        "id": f"chatcmpl_tranquera_blocked_{trace_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": _block_text(hit)},
                "finish_reason": "content_filter",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _chat_sse(data: dict[str, Any] | str) -> bytes:
    if isinstance(data, str):
        return f"data: {data}\n\n".encode()
    return f"data: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


async def synthesize_openai_block_sse(
    model: str, trace_id: str, hit: PolicyHit
) -> AsyncIterator[bytes]:
    chunk_id = f"chatcmpl_tranquera_blocked_{trace_id}"
    created = int(time.time())
    yield _chat_sse(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
    )
    yield _chat_sse(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {"index": 0, "delta": {"content": _block_text(hit)}, "finish_reason": None}
            ],
        }
    )
    yield _chat_sse(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "content_filter"}],
        }
    )
    yield _chat_sse("[DONE]")


def _scrub(text: str, hits: list[PolicyHit]) -> str:
    out = text
    for hit in hits:
        if not hit.matched_text:
            continue
        try:
            out = re.sub(re.escape(hit.matched_text), "[REDACTED]", out)
        except re.error:
            out = out.replace(hit.matched_text, "[REDACTED]")
    return out


def redact_openai_chat_body(
    body_dict: dict[str, Any], hits: list[PolicyHit]
) -> tuple[dict[str, Any], bool]:
    """Redact only evaluable string content and text blocks.

    Returns the mutated copy plus a flag indicating that non-text blocks were
    present and intentionally preserved. The caller can record that flag in
    audit metadata.
    """
    redact_hits = [h for h in hits if h.matched_text]
    if not redact_hits:
        return body_dict, False

    out = copy.deepcopy(body_dict)
    skipped_non_text_blocks = False

    for msg in out.get("messages", []):
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role"))
        if role not in EVALUABLE_OPENAI_ROLES:
            continue
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = _scrub(content, redact_hits)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    skipped_non_text_blocks = True
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    block["text"] = _scrub(block["text"], redact_hits)
                else:
                    skipped_non_text_blocks = True

    return out, skipped_non_text_blocks


def openai_upstream_path(_base_url: str) -> str:
    """Canonical Chat Completions upstream path.

    Upstream base URLs may include `/v1`; the provider client normalizes the
    base URL, so the route path stays stable and never becomes `/v1/v1/...`.
    """
    return OPENAI_CHAT_COMPLETIONS_PATH
