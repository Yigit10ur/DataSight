from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATASIGHT_")

    app_name: str = "AI Data Insight Engine"
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_bytes: int = 100 * 1024 * 1024


settings = Settings()
