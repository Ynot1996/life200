"""Application settings, loaded from environment variables (12-factor style).

Every variable is prefixed with LIFE200_, e.g. LIFE200_DATABASE_URL.
Values come from the real environment first, then from a `.env` file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LIFE200_",
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    env: Literal["local", "test", "prod"] = "local"
    database_url: str = "postgresql+asyncpg://life200:life200@localhost:5432/life200"
    redis_url: str = "redis://localhost:6379/0"
    # SecretStr hides the value in logs and repr() — never print API keys.
    anthropic_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read the environment once)."""
    return Settings()
