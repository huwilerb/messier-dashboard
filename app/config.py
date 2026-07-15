"""Application configuration loaded from environment variables.

Uses pydantic-settings so values can come from the process environment or a
local ``.env`` file (see ``.env.example`` at the repository root for the full
list of supported variables).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

_INSECURE_DEFAULT_SECRET_KEY = "change-me-to-a-long-random-string-at-least-32-chars"


class Settings(BaseSettings):
    """Runtime configuration for the Messier Marathon app."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    SECRET_KEY: str = _INSECURE_DEFAULT_SECRET_KEY
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///data/messier.db"

    # Uploads
    UPLOAD_DIR: str = "app/static/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Business rule: one capture per (groupe, objet) when True.
    UNIQUE_OBSERVATION_PER_OBJECT: bool = True

    @model_validator(mode="after")
    def _reject_insecure_secret_key_outside_debug(self) -> "Settings":
        # The placeholder key is only acceptable for local/DEBUG use. Refuse
        # to boot with it anywhere else, since it lets anyone forge session
        # cookies (including admin sessions) once the value is public.
        if not self.DEBUG and self.SECRET_KEY == _INSECURE_DEFAULT_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY is set to the insecure placeholder value. "
                "Set a unique random SECRET_KEY (see .env.example) before "
                "running with DEBUG=false."
            )
        return self

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (env is read once per process)."""
    return Settings()


settings = get_settings()
