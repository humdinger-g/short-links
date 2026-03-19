from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArchivedLink, Link, utc_now
from app.links.cleanup import (
    delete_expired_links,
    delete_unused_links,
    get_expired_links_history,
)


@pytest.mark.asyncio
async def test_delete_expired_links_archives_and_removes_only_expired(
    db_session: AsyncSession,
) -> None:
    expired_link = Link(
        short_code="expired",
        original_url="https://example.com/expired",
        expires_at=utc_now() - timedelta(minutes=1),
    )
    active_link = Link(
        short_code="active",
        original_url="https://example.com/active",
        expires_at=utc_now() + timedelta(minutes=10),
    )
    db_session.add_all([expired_link, active_link])
    await db_session.commit()

    deleted_links = await delete_expired_links(db_session)

    assert [link.short_code for link in deleted_links] == ["expired"]
    remaining_active = await db_session.get(Link, active_link.id)
    archived_expired = await db_session.get(ArchivedLink, 1)
    assert remaining_active is not None
    assert archived_expired is not None
    assert archived_expired.deletion_reason == "expired"


@pytest.mark.asyncio
async def test_delete_unused_links_removes_old_last_used_and_old_never_used_links(
    db_session: AsyncSession,
) -> None:
    old_used_link = Link(
        short_code="old-used",
        original_url="https://example.com/old-used",
        last_used_at=utc_now() - timedelta(days=40),
    )
    old_never_used_link = Link(
        short_code="old-never-used",
        original_url="https://example.com/old-never-used",
        created_at=utc_now() - timedelta(days=40),
    )
    fresh_link = Link(
        short_code="fresh",
        original_url="https://example.com/fresh",
        last_used_at=utc_now(),
    )
    db_session.add_all([old_used_link, old_never_used_link, fresh_link])
    await db_session.commit()

    deleted_links = await delete_unused_links(db_session, unused_link_days=30)

    assert {link.short_code for link in deleted_links} == {
        "old-used",
        "old-never-used",
    }
    assert await db_session.get(Link, fresh_link.id) is not None


@pytest.mark.asyncio
async def test_delete_unused_links_returns_empty_for_non_positive_days(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        Link(
            short_code="still-there",
            original_url="https://example.com/path",
        )
    )
    await db_session.commit()

    deleted_links = await delete_unused_links(db_session, unused_link_days=0)

    assert deleted_links == []


@pytest.mark.asyncio
async def test_get_expired_links_history_returns_only_expired_items(
    db_session: AsyncSession,
) -> None:
    db_session.add_all(
        [
            ArchivedLink(
                short_code="expired-new",
                original_url="https://example.com/new",
                owner_id=None,
                created_at=utc_now(),
                expires_at=None,
                last_used_at=None,
                click_count=3,
                deletion_reason="expired",
                deleted_at=utc_now(),
            ),
            ArchivedLink(
                short_code="unused",
                original_url="https://example.com/unused",
                owner_id=None,
                created_at=utc_now(),
                expires_at=None,
                last_used_at=None,
                click_count=0,
                deletion_reason="unused",
                deleted_at=utc_now() - timedelta(minutes=1),
            ),
        ]
    )
    await db_session.commit()

    history = await get_expired_links_history(db_session)

    assert [item.short_code for item in history] == ["expired-new"]
