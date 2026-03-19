from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ArchivedLink, Link, utc_now


@pytest.mark.asyncio
async def test_create_search_stats_and_redirect_flow(client: AsyncClient) -> None:
    original_url = "https://example.com/articles/1"
    create_response = await client.post(
        "/links/shorten",
        json={"original_url": original_url, "custom_alias": "article-1"},
    )

    assert create_response.status_code == 201
    assert create_response.json()["short_code"] == "article-1"

    search_response = await client.get(
        "/links/search",
        params={"original_url": original_url},
    )
    assert search_response.status_code == 200
    assert [item["short_code"] for item in search_response.json()] == ["article-1"]

    stats_before_redirect = await client.get("/links/article-1/stats")
    assert stats_before_redirect.status_code == 200
    assert stats_before_redirect.json()["click_count"] == 0

    redirect_response = await client.get("/links/article-1")
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"] == original_url

    stats_after_redirect = await client.get("/links/article-1/stats")
    assert stats_after_redirect.status_code == 200
    assert stats_after_redirect.json()["click_count"] == 1
    assert stats_after_redirect.json()["last_used_at"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"original_url": "not-a-url"},
        {"original_url": "https://example.com/path", "custom_alias": "bad alias"},
        {
            "original_url": "https://example.com/path",
            "expires_at": (utc_now() - timedelta(minutes=1))
            .replace(second=0, microsecond=0)
            .isoformat(),
        },
        {
            "original_url": "https://example.com/path",
            "expires_at": (utc_now() + timedelta(minutes=10))
            .replace(microsecond=0)
            .isoformat(),
        },
    ],
)
async def test_create_link_rejects_invalid_payloads(
    client: AsyncClient,
    payload: dict[str, str],
) -> None:
    response = await client.post("/links/shorten", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_link_rejects_reserved_and_duplicate_aliases(
    client: AsyncClient,
) -> None:
    reserved_alias_response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/path",
            "custom_alias": "search",
        },
    )
    first_alias_response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/path",
            "custom_alias": "shared-alias",
        },
    )
    duplicate_alias_response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/other",
            "custom_alias": "shared-alias",
        },
    )

    assert reserved_alias_response.status_code == 400
    assert first_alias_response.status_code == 201
    assert duplicate_alias_response.status_code == 409


@pytest.mark.asyncio
async def test_owner_can_update_and_delete_link(
    client: AsyncClient,
    make_auth_headers,
) -> None:
    headers = await make_auth_headers()
    create_response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/original",
            "custom_alias": "owned-link",
        },
        headers=headers,
    )
    assert create_response.status_code == 201

    update_response = await client.put(
        "/links/owned-link",
        json={"original_url": "https://example.com/updated"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["original_url"] == "https://example.com/updated"

    delete_response = await client.delete("/links/owned-link", headers=headers)
    assert delete_response.status_code == 204

    stats_response = await client.get("/links/owned-link/stats")
    assert stats_response.status_code == 404


@pytest.mark.asyncio
async def test_link_management_requires_owner(
    client: AsyncClient,
    make_auth_headers,
) -> None:
    create_response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/original",
            "custom_alias": "anonymous-link",
        },
    )
    assert create_response.status_code == 201

    unauthorized_update = await client.put(
        "/links/anonymous-link",
        json={"original_url": "https://example.com/updated"},
    )
    assert unauthorized_update.status_code == 401

    headers = await make_auth_headers()
    forbidden_update = await client.put(
        "/links/anonymous-link",
        json={"original_url": "https://example.com/updated"},
        headers=headers,
    )
    assert forbidden_update.status_code == 403


@pytest.mark.asyncio
async def test_other_user_cannot_manage_foreign_link(
    client: AsyncClient,
    make_auth_headers,
) -> None:
    owner_headers = await make_auth_headers("owner@example.com", "password123")
    stranger_headers = await make_auth_headers("stranger@example.com", "password123")

    create_response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/original",
            "custom_alias": "foreign-link",
        },
        headers=owner_headers,
    )
    assert create_response.status_code == 201

    response = await client.delete("/links/foreign-link", headers=stranger_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_expired_link_is_not_accessible(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    create_response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/path",
            "custom_alias": "expiring-link",
            "expires_at": (
                utc_now().replace(second=0, microsecond=0) + timedelta(minutes=5)
            ).isoformat(),
        },
    )
    assert create_response.status_code == 201

    async with session_maker() as session:
        result = await session.execute(select(Link).where(Link.short_code == "expiring-link"))
        link = result.scalar_one()
        link.expires_at = utc_now() - timedelta(minutes=1)
        await session.commit()

    response = await client.get("/links/expiring-link")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_expired_history_endpoint_returns_only_expired_links(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    db_session.add_all(
        [
            ArchivedLink(
                short_code="expired-link",
                original_url="https://example.com/expired",
                owner_id=None,
                created_at=utc_now(),
                expires_at=utc_now(),
                last_used_at=None,
                click_count=2,
                deletion_reason="expired",
                deleted_at=utc_now(),
            ),
            ArchivedLink(
                short_code="unused-link",
                original_url="https://example.com/unused",
                owner_id=None,
                created_at=utc_now(),
                expires_at=None,
                last_used_at=None,
                click_count=0,
                deletion_reason="unused",
                deleted_at=utc_now(),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/links/history/expired")

    assert response.status_code == 200
    assert [item["short_code"] for item in response.json()] == ["expired-link"]
