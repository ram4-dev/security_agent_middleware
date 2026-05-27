"""Layer 3 — natural-language judge.

The public API stays protocol-neutral: callers pass evaluable text plus NL
policies and receive PolicyHit objects. Provider-specific HTTP details live in
app.judge adapters (Anthropic, OpenAI-compatible/OpenCode Go, Gemini).

The layer is fail-open by design: missing keys, provider errors, timeouts,
malformed JSON, or unknown providers return [] so regex/passthrough behavior is
not blocked by judge availability.
"""

import logging
from typing import Any

from .cascade import PolicyHit, extract_texts
from .config import settings
from .judge.factory import get_judge_provider
from .judge.prompt import (
    JUDGE_MAX_TOKENS as _JUDGE_MAX_TOKENS,
)
from .judge.prompt import (
    JUDGE_SYSTEM as _JUDGE_SYSTEM,
)
from .judge.prompt import (
    JUDGE_TIMEOUT_S as _JUDGE_TIMEOUT_S,
)
from .judge.prompt import (
    build_anthropic_messages,
    format_prompt_texts,
    format_rules_block,
    parse_matched_ids,
    policy_hits_from_ids,
)
from .judge.types import JudgeRequest
from .models import Policy
from .schemas import MessagesRequest

logger = logging.getLogger("app.nl_layer")

# Backwards-compatible constants for tests/imports that reached into nl_layer.
JUDGE_MODEL = "claude-haiku-4-5-20251001"
JUDGE_MAX_TOKENS = _JUDGE_MAX_TOKENS
JUDGE_SYSTEM = _JUDGE_SYSTEM
JUDGE_TIMEOUT_S = _JUDGE_TIMEOUT_S
ANTHROPIC_VERSION = "2023-06-01"


def _format_rules_block(policies: list[Policy]) -> str:
    return format_rules_block(policies)


def _format_prompt_texts(texts: list[str]) -> str:
    return format_prompt_texts(texts)


def _build_judge_messages_for_texts(
    policies: list[Policy], texts: list[str]
) -> list[dict[str, str]]:
    return build_anthropic_messages(policies, texts)


def _build_judge_messages(policies: list[Policy], req: MessagesRequest) -> list[dict[str, Any]]:
    return _build_judge_messages_for_texts(policies, extract_texts(req))


def _parse_matched_ids(content_text: str) -> list[str]:
    return parse_matched_ids(content_text)


def is_enabled() -> bool:
    """True when the configured judge provider has server-side credentials."""
    return get_judge_provider().is_enabled()


async def run_nl_texts(
    texts: list[str],
    policies: list[Policy],
) -> list[PolicyHit]:
    """Run the provider-agnostic NL judge over normalized evaluable text."""
    if not policies:
        return []

    provider = get_judge_provider()
    if not provider.is_enabled():
        return []

    request = JudgeRequest(
        trace_id="",
        org_id=settings.default_org_id,
        texts=texts,
        policies=policies,
    )
    try:
        decision = await provider.judge(request)
    except Exception as exc:  # noqa: BLE001 - fail-open boundary for all provider bugs.
        logger.warning("[judge] provider=%s error=%s", provider.provider, type(exc).__name__)
        return []

    logger.info(
        "[judge] provider=%s model=%s matched_count=%d",
        decision.raw_provider,
        decision.raw_model,
        len(decision.matched_policy_ids),
    )
    return policy_hits_from_ids(decision.matched_policy_ids, policies)


async def run_nl_layer(
    req: MessagesRequest,
    policies: list[Policy],
) -> list[PolicyHit]:
    """Anthropic Messages compatibility wrapper for the protocol-neutral judge."""
    return await run_nl_texts(extract_texts(req), policies)
