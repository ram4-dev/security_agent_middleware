"""Redaction utilities.

Two surfaces:
- `redact_for_storage`   — scrubs the flattened prompt text before INSERT.
                           Runs on every interaction regardless of action.
- `redact_request_body`  — mutates the structured JSON body that will be
                           forwarded to upstream when action=REDACT. Secrets
                           are replaced with [REDACTED] so the model never
                           sees them, but the request still reaches upstream.
"""

import copy
import re
from typing import Any

from .cascade import PolicyHit


def _scrub(text: str, hits: list[PolicyHit]) -> str:
    """Replace every matched_text with [REDACTED] (generic, no slug leak)."""
    out = text
    for hit in hits:
        if not hit.matched_text:
            continue
        try:
            out = re.sub(re.escape(hit.matched_text), "[REDACTED]", out)
        except re.error:
            out = out.replace(hit.matched_text, "[REDACTED]")
    return out


def redact_for_storage(text: str, hits: list[PolicyHit]) -> str:
    """Scrub prompt text for the audit trail (slug included for traceability)."""
    out = text
    for hit in hits:
        if not hit.matched_text:
            continue
        replacement = f"[REDACTED:{hit.slug}]"
        try:
            out = re.sub(re.escape(hit.matched_text), replacement, out)
        except re.error:
            out = out.replace(hit.matched_text, replacement)
    return out


def redact_request_body(body_dict: dict[str, Any], hits: list[PolicyHit]) -> dict[str, Any]:
    """Return a deep copy of body_dict with all matched secrets scrubbed.

    Walks every text field in messages and system so the mutated body is
    safe to forward to the Anthropic upstream.
    """
    redact_hits = [h for h in hits if h.matched_text]
    if not redact_hits:
        return body_dict

    out = copy.deepcopy(body_dict)

    # --- system field ---
    sys = out.get("system")
    if isinstance(sys, str):
        out["system"] = _scrub(sys, redact_hits)
    elif isinstance(sys, list):
        for block in sys:
            if isinstance(block, dict) and block.get("type") == "text":
                block["text"] = _scrub(block["text"], redact_hits)

    # --- messages ---
    for msg in out.get("messages", []):
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = _scrub(content, redact_hits)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    block["text"] = _scrub(block["text"], redact_hits)

    return out
