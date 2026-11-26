"""App settings, read from backend/.env. Real environment variables win over the file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str
    test_database_url: str | None = None
    jwt_secret: str
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    # How long a just-rotated refresh token may be presented again (two tabs
    # refreshing at once) before it counts as reuse and revokes the family.
    refresh_reuse_grace_seconds: int = 30
    # Send cookies only over HTTPS. Turn on in production.
    cookie_secure: bool = False
    # How long a workspace invite link works.
    invite_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
