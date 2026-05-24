import logging
from typing import Any

from app.config import settings
from app.judge.anthropic import (
    DEFAULT_ANTHROPIC_BASE_URL,
    DEFAULT_ANTHROPIC_MODEL,
    AnthropicJudgeProvider,
)
from app.judge.gemini import DEFAULT_GEMINI_BASE_URL, DEFAULT_GEMINI_MODEL, GeminiJudgeProvider
from app.judge.openai_compatible import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENCODE_GO_BASE_URL,
    DEFAULT_OPENCODE_GO_MODEL,
    OpenAICompatibleJudgeProvider,
)
from app.judge.types import JudgeDecision, JudgeProvider, JudgeRequest

logger = logging.getLogger("app.judge.factory")


class DisabledJudgeProvider:
    provider = "disabled"

    def __init__(self, reason: str = "missing_credentials") -> None:
        self.reason = reason

    def is_enabled(self) -> bool:
        return False

    async def judge(self, req: JudgeRequest) -> JudgeDecision:
        return JudgeDecision([], self.provider, "")


def _setting(config: Any, name: str, default: Any = None) -> Any:
    return getattr(config, name, default)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def get_judge_provider(config: Any = settings) -> JudgeProvider:
    """Resolve the configured judge provider, preserving legacy Anthropic envs."""
    configured_provider = _clean(_setting(config, "judge_provider"))
    legacy_key = _clean(_setting(config, "anthropic_judge_api_key"))
    provider = (configured_provider or "anthropic").lower()

    if provider == "anthropic":
        api_key = _clean(_setting(config, "judge_api_key")) or legacy_key
        if not api_key:
            return DisabledJudgeProvider("missing_credentials")
        return AnthropicJudgeProvider(
            api_key=api_key,
            base_url=(
                _clean(_setting(config, "judge_base_url"))
                or _clean(_setting(config, "anthropic_upstream_url"))
                or DEFAULT_ANTHROPIC_BASE_URL
            ),
            model=_clean(_setting(config, "judge_model")) or DEFAULT_ANTHROPIC_MODEL,
        )

    if provider not in {"opencode-go", "openai", "gemini"}:
        logger.warning("[judge] disabled unknown_provider=%s", provider)
        return DisabledJudgeProvider("unknown_provider")

    api_key = _clean(_setting(config, "judge_api_key"))
    if not api_key:
        return DisabledJudgeProvider("missing_credentials")

    if provider == "opencode-go":
        return OpenAICompatibleJudgeProvider(
            provider=provider,
            api_key=api_key,
            base_url=_clean(_setting(config, "judge_base_url")) or DEFAULT_OPENCODE_GO_BASE_URL,
            model=_clean(_setting(config, "judge_model")) or DEFAULT_OPENCODE_GO_MODEL,
        )

    if provider == "openai":
        return OpenAICompatibleJudgeProvider(
            provider=provider,
            api_key=api_key,
            base_url=_clean(_setting(config, "judge_base_url")) or DEFAULT_OPENAI_BASE_URL,
            model=_clean(_setting(config, "judge_model")) or DEFAULT_OPENAI_MODEL,
        )

    if provider == "gemini":
        return GeminiJudgeProvider(
            api_key=api_key,
            base_url=_clean(_setting(config, "judge_base_url")) or DEFAULT_GEMINI_BASE_URL,
            model=_clean(_setting(config, "judge_model")) or DEFAULT_GEMINI_MODEL,
        )

    return DisabledJudgeProvider("unknown_provider")
