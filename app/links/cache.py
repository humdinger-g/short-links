from datetime import datetime, timezone

from app.cache import (
    build_link_stats_cache_key,
    build_links_search_cache_key,
    delete_cache_keys,
    get_json_cache,
    set_json_cache,
)
from app.db.models import Link
from app.links.schemas import LinkRead, LinkStatsRead
from app.settings import get_settings


def _link_cache_ttl_seconds(link: Link) -> int:
    default_ttl = get_settings().cache_ttl_seconds
    if link.expires_at is None:
        return default_ttl

    remaining_seconds = int(
        (link.expires_at - datetime.now(timezone.utc)).total_seconds()
    )
    return max(1, min(default_ttl, remaining_seconds))


def _links_cache_ttl_seconds(links: list[Link]) -> int:
    default_ttl = get_settings().cache_ttl_seconds
    expiring_links = [link for link in links if link.expires_at is not None]
    if not expiring_links:
        return default_ttl

    earliest_expiring_link = min(expiring_links, key=lambda link: link.expires_at)
    return _link_cache_ttl_seconds(earliest_expiring_link)


async def get_cached_stats(short_code: str) -> dict | None:
    cached_value = await get_json_cache(build_link_stats_cache_key(short_code))
    if cached_value is None or not isinstance(cached_value, dict):
        return None
    return cached_value


async def set_cached_stats(link: Link) -> dict:
    payload = LinkStatsRead.model_validate(link).model_dump(mode="json")
    await set_json_cache(
        build_link_stats_cache_key(link.short_code),
        payload,
        ttl_seconds=_link_cache_ttl_seconds(link),
    )
    return payload


async def get_cached_search(original_url: str) -> list[dict] | None:
    cached_value = await get_json_cache(build_links_search_cache_key(original_url))
    if cached_value is None or not isinstance(cached_value, list):
        return None
    return cached_value


async def set_cached_search(links: list[Link], original_url: str) -> list[dict]:
    payload = [LinkRead.model_validate(link).model_dump(mode="json") for link in links]
    await set_json_cache(
        build_links_search_cache_key(original_url),
        payload,
        ttl_seconds=_links_cache_ttl_seconds(links),
    )
    return payload


async def invalidate_link_caches(
    *,
    short_code: str | None = None,
    original_urls: list[str] | None = None,
) -> None:
    keys: list[str] = []
    if short_code is not None:
        keys.append(build_link_stats_cache_key(short_code))
    if original_urls is not None:
        keys.extend(build_links_search_cache_key(url) for url in original_urls)
    await delete_cache_keys(*keys)
