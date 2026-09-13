from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATASIGHT_", env_file=".env")

    app_name: str = "AI Data Insight Engine"
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_bytes: int = 100 * 1024 * 1024

    # Explaining a finding is a writing task over numbers that are already settled,
    # so it does not need the largest model.
    explanation_model: str = "claude-sonnet-5"
    explanation_max_insights: int = 8
    explanation_max_tokens: int = 1500
    explanation_timeout_seconds: float = 30.0
    anthropic_api_key: str = ""


settings = Settings()
