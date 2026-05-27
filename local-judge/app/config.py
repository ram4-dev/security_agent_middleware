from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    local_judge_service_host: str = "0.0.0.0"
    local_judge_service_port: int = 8088
    local_judge_vllm_base_url: str = "http://localhost:8000/v1"
    local_judge_vllm_model: str = "Qwen/Qwen3-4B-Instruct-2507"
    local_judge_prompt_version: str = "local_judge_v1"
    local_judge_max_input_chars: int = 30_000
    local_judge_max_output_tokens: int = 512
    local_judge_temperature: float = 0
    local_judge_top_p: float = 1
    local_judge_json_mode: bool = True
    local_judge_request_timeout_ms: int = 700
    local_judge_risk_taxonomy_version: str = "risk_taxonomy_v1"
    local_judge_explanation_max_chars: int = Field(default=500, ge=1)


settings = Settings()
