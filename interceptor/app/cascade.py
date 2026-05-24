"""Layer 1 — regex cascade.

Compiles each policy's pattern once per request batch and scans the
extracted prompt texts. A single hit per policy is enough; we don't try
to count occurrences.
"""

import re
from dataclasses import dataclass
from typing import Any

from .enums import Action, PolicyLayer
from .models import Policy
from .protocols import TextPart
from .schemas import MessagesRequest


@dataclass
class PolicyHit:
    policy_id: str
    slug: str
    layer: PolicyLayer
    action: Action
    rule: str
    matched_text: str

    def to_record(self) -> dict[str, Any]:
        """Shape persisted in interactions.policy_hits (no matched text — leak risk)."""
        return {
            "layer": self.layer.value,
            "policy_id": self.policy_id,
            "slug": self.slug,
            "action": self.action.value,
        }


def extract_text_parts(req: MessagesRequest) -> list[TextPart]:
    """Pull every user-authored string from the request body.

    System prompts are author-controlled today but admins may inline
    secrets in them, so we scan those too.
    """
    parts: list[TextPart] = []

    if isinstance(req.system, str):
        parts.append(TextPart("system", "system", req.system))
    elif isinstance(req.system, list):
        for index, block in enumerate(req.system):
            if block.get("type") == "text" and block.get("text"):
                parts.append(TextPart(f"system[{index}].text", "system", block.get("text", "")))

    for msg_index, msg in enumerate(req.messages):
        if isinstance(msg.content, str):
            if msg.content:
                parts.append(TextPart(f"messages[{msg_index}].content", msg.role, msg.content))
        else:
            for block_index, block in enumerate(msg.content):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(
                        TextPart(
                            f"messages[{msg_index}].content[{block_index}].text",
                            msg.role,
                            block.get("text", ""),
                        )
                    )

    return parts


def extract_texts(req: MessagesRequest) -> list[str]:
    return [part.text for part in extract_text_parts(req) if part.text]


def _as_layer(v: object) -> PolicyLayer:
    return v if isinstance(v, PolicyLayer) else PolicyLayer(v)


def _as_action(v: object) -> Action:
    return v if isinstance(v, Action) else Action(v)


def run_regex_texts(texts: list[str], policies: list[Policy]) -> list[PolicyHit]:
    hits: list[PolicyHit] = []

    for policy in policies:
        layer = _as_layer(policy.layer)
        if layer != PolicyLayer.regex or not policy.pattern:
            continue
        try:
            compiled = re.compile(policy.pattern)
        except re.error:
            # A malformed pattern shouldn't crash the proxy; skip it.
            continue
        for text in texts:
            match = compiled.search(text)
            if match:
                hits.append(
                    PolicyHit(
                        policy_id=str(policy.id),
                        slug=policy.slug,
                        layer=layer,
                        action=_as_action(policy.default_action),
                        rule=policy.rule,
                        matched_text=match.group(0),
                    )
                )
                break

    return hits


def run_regex_layer(req: MessagesRequest, policies: list[Policy]) -> list[PolicyHit]:
    return run_regex_texts(extract_texts(req), policies)
