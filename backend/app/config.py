from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI Data Insight Engine"
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_bytes: int = 100 * 1024 * 1024

    class Config:
        env_prefix = "DATASIGHT_"


settings = Settings()
