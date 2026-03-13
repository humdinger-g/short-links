import secrets
import string

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Link, User, utc_now
from app.links.schemas import LinkCreateRequest


RESERVED_CODES = {"search", "shorten"}
SHORT_CODE_LENGTH = 8
SHORT_CODE_ALPHABET = string.ascii_letters + string.digits


def generate_short_code(length: int = SHORT_CODE_LENGTH) -> str:
    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(length))


async def get_active_link_by_code(
    session: AsyncSession,
    short_code: str,
) -> Link | None:
    now = utc_now()
    result = await session.execute(
        select(Link).where(
            Link.short_code == short_code,
            or_(Link.expires_at.is_(None), Link.expires_at > now),
        )
    )
    return result.scalar_one_or_none()


async def search_active_links_by_original_url(
    session: AsyncSession,
    original_url: str,
) -> list[Link]:
    now = utc_now()
    result = await session.execute(
        select(Link)
        .where(
            Link.original_url == original_url,
            or_(Link.expires_at.is_(None), Link.expires_at > now),
        )
        .order_by(Link.created_at.desc())
    )
    return list(result.scalars().all())


async def ensure_custom_alias_available(
    session: AsyncSession,
    alias: str,
) -> None:
    result = await session.execute(select(Link.id).where(Link.short_code == alias))
    existing_link_id = result.scalar_one_or_none()
    if existing_link_id is not None:
        raise ValueError("This custom alias is already in use.")


async def create_link(
    session: AsyncSession,
    payload: LinkCreateRequest,
    owner: User | None,
) -> Link:
    original_url = str(payload.original_url)
    owner_id = owner.id if owner is not None else None

    if payload.custom_alias is not None:
        alias = payload.custom_alias
        if alias.lower() in RESERVED_CODES:
            raise ValueError("This custom alias is reserved.")
        await ensure_custom_alias_available(session, alias)
        link = Link(
            short_code=alias,
            original_url=original_url,
            owner_id=owner_id,
            expires_at=payload.expires_at,
        )
        session.add(link)
        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            raise ValueError("This custom alias is already in use.") from error
        await session.refresh(link)
        return link

    for _ in range(20):
        short_code = generate_short_code()
        if short_code.lower() in RESERVED_CODES:
            continue

        link = Link(
            short_code=short_code,
            original_url=original_url,
            owner_id=owner_id,
            expires_at=payload.expires_at,
        )
        session.add(link)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            continue
        await session.refresh(link)
        return link

    raise RuntimeError("Could not generate a unique short code.")


def ensure_user_can_manage_link(link: Link, user: User) -> None:
    if link.owner_id is None or link.owner_id != user.id:
        raise PermissionError("You do not have permission to manage this link.")
