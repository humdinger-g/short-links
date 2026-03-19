from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Short Links"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/short_links"
    redis_url: str = "redis://redis:6379/0"
    public_base_url: str = "http://localhost:8000"
    auth_secret: str = "change-me"
    access_token_ttl_minutes: int = 60
    cache_ttl_seconds: int = 300
    expired_links_cleanup_interval_seconds: int = 60
    unused_link_days: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
