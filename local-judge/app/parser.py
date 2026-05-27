from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .schemas import LocalJudgeResponse

_SECRETISH_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"[A-Za-z0-9_]*(?:SECRET|TOKEN|API_KEY)[A-Za-z0-9_]*=\S+", re.IGNORECASE),
]


class ModelOutputError(ValueError):
    pass


def parse_model_output(raw: str, *, default_model_version: str) -> LocalJudgeResponse:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ModelOutputError("model output is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise ModelOutputError("model output must be a JSON object")

    payload.setdefault("model_version", default_model_version)

    try:
        response = LocalJudgeResponse.model_validate(payload)
    except ValidationError as exc:
        raise ModelOutputError("model output failed schema validation") from exc

    if _contains_secretish_text(response.explanation):
        raise ModelOutputError("model explanation contains secret-like text")

    return response


def _contains_secretish_text(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRETISH_PATTERNS)


def error_payload(error: str, trace_id: str | None) -> dict[str, Any]:
    return {"error": error, "trace_id": trace_id}
