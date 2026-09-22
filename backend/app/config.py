from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved from this file rather than the working directory. A relative ".env"
# is read against wherever the process was started, so the key loaded when the
# server was launched from backend/ and silently did not when anything ran from
# the repository root — leaving the explanation layer off with no error to read.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATASIGHT_", env_file=ENV_FILE)

    app_name: str = "AI Data Insight Engine"
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    dataset_ttl_seconds: float = Field(default=3600, gt=0, allow_inf_nan=False)
    max_datasets: int = Field(default=100, gt=0)
    dashboard_cache_size: int = Field(default=16, gt=0)
    question_max_turns: int = Field(default=10, gt=0)

    # Explaining a finding is a writing task over numbers that are already settled,
    # so it does not need the largest model.
    explanation_model: str = "claude-sonnet-5"
    explanation_max_insights: int = 8
    explanation_max_tokens: int = 1500
    explanation_timeout_seconds: float = 30.0
    anthropic_api_key: str = ""


settings = Settings()
