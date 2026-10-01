from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved from this file rather than the working directory. A relative ".env"
# is read against wherever the process was started, so settings loaded when the
# server was launched from backend/ and silently did not when anything ran from
# the repository root.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
DEFAULT_DATABASE = Path(__file__).resolve().parent.parent / "datasight.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATASIGHT_", env_file=ENV_FILE)

    app_name: str = "DataSight"
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    # What an .xlsx may unpack to. A workbook is a zip of XML, and reading it takes
    # about 3 bytes of memory and 0.2 seconds per unpacked megabyte: a few MB of
    # repetitive cells can unpack to gigabytes.
    max_workbook_bytes: int = Field(default=128 * 1024 * 1024, gt=0)
    dataset_ttl_seconds: float = Field(default=3600, gt=0, allow_inf_nan=False)
    max_datasets: int = Field(default=100, gt=0)
    # What the stored frames may occupy in memory, counted as pandas measures them.
    # The dataset count alone bounds nothing: one 25 MB CSV parsed to 154 MB.
    max_store_bytes: int = Field(default=1024 * 1024 * 1024, gt=0)
    # How many parses, analyses, and recipe runs may run at once. Each can take a
    # few times its frame's size while it works, so this bounds the memory that is
    # in flight, where max_store_bytes bounds the memory that is kept.
    max_concurrent_jobs: int = Field(default=2, gt=0)
    # One account's share of the limits above, so a single sign-up cannot fill the
    # store for everyone else.
    max_user_store_bytes: int = Field(default=256 * 1024 * 1024, gt=0)
    max_datasets_per_user: int = Field(default=20, gt=0)
    dashboard_cache_size: int = Field(default=16, gt=0)
    # Accounts and sessions are kept in this SQLite file, unlike datasets, so they
    # survive a restart.
    database_path: Path = DEFAULT_DATABASE
    session_ttl_seconds: int = Field(default=7 * 24 * 3600, gt=0)
    # Sends the session cookie over HTTPS only. Off by default because local
    # development runs on plain http; the deployment turns it on.
    secure_cookies: bool = False
    # Serves /docs, /redoc, and /openapi.json. Turn off where the API is public.
    api_docs: bool = True


settings = Settings()
