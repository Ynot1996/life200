"""Application settings, loaded from environment variables (12-factor style).

Every variable is prefixed with LIFE200_, e.g. LIFE200_DATABASE_URL.
Values come from the real environment first, then from a `.env` file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LIFE200_",
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    env: Literal["local", "test", "prod"] = "local"
    # psycopg is the Postgres driver SQLAlchemy uses to talk to the database.
    database_url: str = "postgresql+psycopg://life200:life200@localhost:5432/life200"
    redis_url: str = "redis://localhost:6379/0"
    # SecretStr hides the value in logs and repr() — never print API keys.
    anthropic_api_key: SecretStr | None = None
    adzuna_app_id: str | None = None
    adzuna_app_key: SecretStr | None = None
    # Jooble keys only work on the country site that issued them: Taiwan needs a tw.jooble.org key.
    jooble_tw_key: SecretStr | None = None
    claude_model: str = "claude-opus-5-5"
    # Gemini is used when there is no Anthropic key. Free keys: aistudio.google.com.
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"  # newest Flash on the API as of 2026-11-20
    gemini_fallback_model: str | None = "gemini-3.7-flash"  # used when the main one is overloaded

    @field_validator("*", mode="before")
    @classmethod
    def _blank_is_missing(cls, value: object) -> object:
        """`KEY=` in .env means "not set", not "set to an empty string"."""
        return None if isinstance(value, str) and not value.strip() else value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read the environment once)."""
    return Settings()
