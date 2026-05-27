from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import settings
from .schemas import LocalJudgeRequest

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=8)
def load_system_prompt(prompt_version: str) -> str:
    path = _PROMPTS_DIR / f"{prompt_version}.md"
    return path.read_text(encoding="utf-8")


def build_messages(request: LocalJudgeRequest) -> list[dict[str, str]]:
    serialized = json.dumps(
        request.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(serialized) > settings.local_judge_max_input_chars:
        serialized = serialized[: settings.local_judge_max_input_chars]

    return [
        {"role": "system", "content": load_system_prompt(settings.local_judge_prompt_version)},
        {"role": "user", "content": serialized},
    ]
