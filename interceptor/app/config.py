from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Required — no default. Missing env var must fail at boot, not silently
    # connect to whatever DB the developer happened to set last.
    database_url: str

    # Public/non-sensitive defaults are fine.
    anthropic_upstream_url: str = "https://api.anthropic.com"
    default_org_id: str = "demo"
    host: str = "0.0.0.0"
    port: int = 8080


settings = Settings()
