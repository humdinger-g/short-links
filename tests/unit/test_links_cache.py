from datetime import timedelta

import pytest

import app.cache as cache_module
from app.cache import (
    build_link_stats_cache_key,
    build_links_search_cache_key,
    delete_cache_keys,
    get_json_cache,
    set_json_cache,
)
from app.db.models import Link, utc_now
from app.links.cache import (
    _link_cache_ttl_seconds,
    _links_cache_ttl_seconds,
    get_cached_search,
    get_cached_stats,
    invalidate_link_caches,
    set_cached_search,
    set_cached_stats,
)
from app.settings import get_settings


def test_cache_key_builders_use_expected_format() -> None:
    assert build_link_stats_cache_key("abc") == "link:stats:abc"
    assert (
        build_links_search_cache_key("https://example.com/path")
        == "links:search:https://example.com/path"
    )


def test_get_redis_client_builds_client_from_settings_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    cache_module.get_redis_client.cache_clear()
    monkeypatch.setattr(cache_module.Redis, "from_url", lambda *args, **kwargs: sentinel)

    assert cache_module.get_redis_client() is sentinel


@pytest.mark.asyncio
async def test_json_cache_roundtrip_and_delete(fake_redis) -> None:
    await set_json_cache("example:key", {"value": 1})

    assert await get_json_cache("example:key") == {"value": 1}

    await delete_cache_keys("example:key")

    assert await get_json_cache("example:key") is None


def test_link_cache_ttl_uses_default_for_non_expiring_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cache_ttl_seconds", 300)
    link = Link(
        short_code="code",
        original_url="https://example.com/path",
        expires_at=None,
    )

    assert _link_cache_ttl_seconds(link) == 300


def test_link_cache_ttl_caps_by_remaining_lifetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cache_ttl_seconds", 300)
    link = Link(
        short_code="code",
        original_url="https://example.com/path",
        expires_at=utc_now() + timedelta(seconds=20),
    )

    assert 1 <= _link_cache_ttl_seconds(link) <= 20


def test_links_cache_ttl_uses_earliest_expiring_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cache_ttl_seconds", 300)
    links = [
        Link(
            short_code="later",
            original_url="https://example.com/1",
            expires_at=utc_now() + timedelta(minutes=5),
        ),
        Link(
            short_code="sooner",
            original_url="https://example.com/2",
            expires_at=utc_now() + timedelta(seconds=15),
        ),
    ]

    assert 1 <= _links_cache_ttl_seconds(links) <= 15


@pytest.mark.asyncio
async def test_link_specific_cache_helpers_roundtrip(fake_redis) -> None:
    link = Link(
        short_code="cached",
        original_url="https://example.com/path",
        created_at=utc_now(),
        expires_at=None,
        last_used_at=None,
        click_count=0,
    )

    cached_stats = await set_cached_stats(link)
    cached_search = await set_cached_search([link], link.original_url)

    assert await get_cached_stats("cached") == cached_stats
    assert await get_cached_search(link.original_url) == cached_search


@pytest.mark.asyncio
async def test_invalidate_link_caches_removes_related_entries(fake_redis) -> None:
    await set_json_cache("link:stats:cached", {"value": 1})
    await set_json_cache("links:search:https://example.com/path", [{"value": 2}])

    await invalidate_link_caches(
        short_code="cached",
        original_urls=["https://example.com/path"],
    )

    assert fake_redis.storage == {}


@pytest.mark.asyncio
async def test_delete_cache_keys_ignores_empty_input(fake_redis) -> None:
    await delete_cache_keys("", None)  # type: ignore[arg-type]

    assert fake_redis.storage == {}
