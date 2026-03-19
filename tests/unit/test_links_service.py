from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Link, User, utc_now
from app.links.schemas import LinkCreateRequest
from app.links.service import (
    SHORT_CODE_ALPHABET,
    SHORT_CODE_LENGTH,
    create_link,
    ensure_user_can_manage_link,
    generate_short_code,
    get_active_link_by_code,
    search_active_links_by_original_url,
)
import app.links.service as links_service_module


def test_generate_short_code_has_expected_shape() -> None:
    short_code = generate_short_code()

    assert len(short_code) == SHORT_CODE_LENGTH
    assert set(short_code).issubset(set(SHORT_CODE_ALPHABET))


@pytest.mark.asyncio
async def test_create_link_with_custom_alias_persists_owner(
    db_session: AsyncSession,
) -> None:
    owner = User(email="owner@example.com", password_hash="hash")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    payload = LinkCreateRequest(
        original_url="https://example.com/path",
        custom_alias="custom-link",
    )

    link = await create_link(db_session, payload, owner)

    assert link.short_code == "custom-link"
    assert link.owner_id == owner.id


@pytest.mark.asyncio
async def test_create_link_rejects_reserved_alias(db_session: AsyncSession) -> None:
    payload = LinkCreateRequest(
        original_url="https://example.com/path",
        custom_alias="search",
    )

    with pytest.raises(ValueError, match="reserved"):
        await create_link(db_session, payload, None)


@pytest.mark.asyncio
async def test_create_link_rejects_duplicate_custom_alias(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        Link(
            short_code="taken",
            original_url="https://example.com/first",
        )
    )
    await db_session.commit()

    payload = LinkCreateRequest(
        original_url="https://example.com/second",
        custom_alias="taken",
    )

    with pytest.raises(ValueError, match="already in use"):
        await create_link(db_session, payload, None)


@pytest.mark.asyncio
async def test_create_link_retries_when_generated_code_collides(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session.add(
        Link(
            short_code="taken",
            original_url="https://example.com/existing",
        )
    )
    await db_session.commit()

    generated_codes = iter(["taken", "fresh-code"])
    monkeypatch.setattr(
        links_service_module,
        "generate_short_code",
        lambda length=SHORT_CODE_LENGTH: next(generated_codes),
    )

    payload = LinkCreateRequest(original_url="https://example.com/new")
    link = await create_link(db_session, payload, None)

    assert link.short_code == "fresh-code"


@pytest.mark.asyncio
async def test_get_active_link_by_code_skips_expired_links(
    db_session: AsyncSession,
) -> None:
    active_link = Link(
        short_code="active",
        original_url="https://example.com/active",
    )
    expired_link = Link(
        short_code="expired",
        original_url="https://example.com/expired",
        expires_at=utc_now() - timedelta(minutes=1),
    )
    db_session.add_all([active_link, expired_link])
    await db_session.commit()

    assert await get_active_link_by_code(db_session, "active") is not None
    assert await get_active_link_by_code(db_session, "expired") is None


@pytest.mark.asyncio
async def test_search_active_links_by_original_url_returns_only_active_links(
    db_session: AsyncSession,
) -> None:
    original_url = "https://example.com/shared"
    active_link = Link(short_code="first", original_url=original_url)
    expired_link = Link(
        short_code="second",
        original_url=original_url,
        expires_at=utc_now() - timedelta(minutes=1),
    )
    db_session.add_all([active_link, expired_link])
    await db_session.commit()

    found_links = await search_active_links_by_original_url(db_session, original_url)

    assert [link.short_code for link in found_links] == ["first"]


def test_ensure_user_can_manage_link_checks_owner() -> None:
    owner = User(id=uuid4(), email="owner@example.com", password_hash="hash")
    stranger = User(id=uuid4(), email="stranger@example.com", password_hash="hash")
    link = Link(
        short_code="owned",
        original_url="https://example.com/path",
        owner_id=owner.id,
    )

    ensure_user_can_manage_link(link, owner)

    with pytest.raises(PermissionError, match="do not have permission"):
        ensure_user_can_manage_link(link, stranger)


def test_ensure_user_can_manage_link_rejects_anonymous_link() -> None:
    user = User(id=uuid4(), email="user@example.com", password_hash="hash")
    anonymous_link = Link(
        short_code="anonymous",
        original_url="https://example.com/path",
        owner_id=None,
    )

    with pytest.raises(PermissionError, match="do not have permission"):
        ensure_user_can_manage_link(anonymous_link, user)
