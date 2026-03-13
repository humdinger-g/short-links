import json
from functools import lru_cache

from redis.asyncio import Redis

from app.settings import get_settings


@lru_cache
def get_redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def build_link_stats_cache_key(short_code: str) -> str:
    return f"link:stats:{short_code}"


def build_links_search_cache_key(original_url: str) -> str:
    return f"links:search:{original_url}"


async def get_json_cache(key: str) -> dict | list | None:
    cached_value = await get_redis_client().get(key)
    if cached_value is None:
        return None
    return json.loads(cached_value)


async def set_json_cache(
    key: str,
    value: dict | list,
    *,
    ttl_seconds: int | None = None,
) -> None:
    await get_redis_client().set(
        key,
        json.dumps(value),
        ex=ttl_seconds or get_settings().cache_ttl_seconds,
    )


async def delete_cache_keys(*keys: str) -> None:
    cache_keys = [key for key in keys if key]
    if not cache_keys:
        return
    await get_redis_client().delete(*cache_keys)
