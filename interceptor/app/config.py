from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required — no default. Missing env var must fail at boot, not silently
    # connect to whatever DB the developer happened to set last.
    database_url: str

    # Public/non-sensitive defaults are fine.
    anthropic_upstream_url: str = "https://api.anthropic.com"
    openai_compat_upstream_url: str = "https://api.openai.com/v1"
    openai_compat_provider: str = "openai"
    openai_compat_integration: str = "openai-compatible"
    default_org_id: str = "demo"
    host: str = "0.0.0.0"
    port: int = 8080

    # Unified NL judge config (Layer 3). If no judge credentials are set, the
    # NL layer is disabled and the proxy keeps running regex + passthrough.
    judge_provider: str | None = None
    judge_base_url: str | None = None
    judge_model: str | None = None
    judge_api_key: str | None = None

    # Legacy Anthropic judge config. Kept for backwards compatibility:
    # ANTHROPIC_JUDGE_API_KEY + ANTHROPIC_UPSTREAM_URL behaves like
    # JUDGE_PROVIDER=anthropic with the equivalent JUDGE_* values.
    anthropic_judge_api_key: str | None = None

    # Optional Specialized Local Judge (spec 17). Disabled by default so the
    # existing regex + NL judge cascade remains unchanged until explicitly
    # enabled in a deployment.
    local_judge_enabled: bool = False
    local_judge_base_url: str | None = "http://localhost:8088"
    local_judge_timeout_ms: int = 800
    local_judge_confidence_threshold: float = 0.75
    local_judge_high_risk_threshold: float = 0.90
    local_judge_model_version: str = "qwen3-4b-localjudge-prompt-v1"
    local_judge_fail_open: bool = True


settings = Settings()
