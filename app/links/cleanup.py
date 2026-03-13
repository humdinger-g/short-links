from datetime import timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArchivedLink, Link, utc_now


def _archive_link(link: Link, deletion_reason: str) -> ArchivedLink:
    return ArchivedLink(
        short_code=link.short_code,
        original_url=link.original_url,
        owner_id=link.owner_id,
        created_at=link.created_at,
        expires_at=link.expires_at,
        last_used_at=link.last_used_at,
        click_count=link.click_count,
        deletion_reason=deletion_reason,
    )


async def _archive_and_delete_links(
    session: AsyncSession,
    links: list[Link],
    deletion_reason: str,
) -> list[Link]:
    if not links:
        return []

    for link in links:
        session.add(_archive_link(link, deletion_reason))
        await session.delete(link)
    await session.commit()
    return links


async def delete_expired_links(session: AsyncSession) -> list[Link]:
    result = await session.execute(
        select(Link).where(
            Link.expires_at.is_not(None),
            Link.expires_at <= utc_now(),
        )
    )
    expired_links = list(result.scalars().all())
    return await _archive_and_delete_links(session, expired_links, "expired")


async def delete_unused_links(
    session: AsyncSession,
    unused_link_days: int,
) -> list[Link]:
    if unused_link_days <= 0:
        return []

    now = utc_now()
    threshold = now - timedelta(days=unused_link_days)
    result = await session.execute(
        select(Link).where(
            or_(Link.expires_at.is_(None), Link.expires_at > now),
            or_(
                Link.last_used_at <= threshold,
                and_(
                    Link.last_used_at.is_(None),
                    Link.created_at <= threshold,
                ),
            ),
        )
    )
    unused_links = list(result.scalars().all())
    return await _archive_and_delete_links(session, unused_links, "unused")


async def get_expired_links_history(session: AsyncSession) -> list[ArchivedLink]:
    result = await session.execute(
        select(ArchivedLink)
        .where(ArchivedLink.deletion_reason == "expired")
        .order_by(ArchivedLink.deleted_at.desc())
    )
    return list(result.scalars().all())
