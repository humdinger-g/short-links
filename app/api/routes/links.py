from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from pydantic import AnyHttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_optional_user
from app.db.models import ArchivedLink, Link, User, utc_now
from app.db.session import get_db_session
from app.links.cache import (
    get_cached_search,
    get_cached_stats,
    invalidate_link_caches,
    set_cached_search,
    set_cached_stats,
)
from app.links.cleanup import get_expired_links_history
from app.links.schemas import (
    ArchivedLinkRead,
    LinkCreateRequest,
    LinkRead,
    LinkStatsRead,
    LinkUpdateRequest,
)
from app.links.service import (
    create_link,
    ensure_user_can_manage_link,
    get_active_link_by_code,
    search_active_links_by_original_url,
)


router = APIRouter(prefix="/links", tags=["links"])


@router.post(
    "/shorten",
    response_model=LinkRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_short_link(
    payload: LinkCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_user),
) -> Link:
    try:
        link = await create_link(session, payload, current_user)
    except ValueError as error:
        status_code = status.HTTP_409_CONFLICT
        if "reserved" in str(error).lower():
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    await invalidate_link_caches(original_urls=[link.original_url])
    return link


@router.get("/search", response_model=list[LinkRead])
async def search_links(
    original_url: AnyHttpUrl = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> list[Link] | list[dict]:
    original_url_str = str(original_url)
    cached_links = await get_cached_search(original_url_str)
    if cached_links is not None:
        return cached_links

    links = await search_active_links_by_original_url(session, original_url_str)
    return await set_cached_search(links, original_url_str)


@router.get("/history/expired", response_model=list[ArchivedLinkRead])
async def get_expired_links(
    session: AsyncSession = Depends(get_db_session),
) -> list[ArchivedLink]:
    return await get_expired_links_history(session)


@router.get("/{short_code}/stats", response_model=LinkStatsRead)
async def get_link_stats(
    short_code: str,
    session: AsyncSession = Depends(get_db_session),
) -> Link | dict:
    cached_stats = await get_cached_stats(short_code)
    if cached_stats is not None:
        return cached_stats

    link = await get_active_link_by_code(session, short_code)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found.",
        )
    return await set_cached_stats(link)


@router.get("/{short_code}")
async def redirect_to_original_url(
    short_code: str,
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    link = await get_active_link_by_code(session, short_code)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found.",
        )

    link.click_count += 1
    link.last_used_at = utc_now()
    await session.commit()
    await invalidate_link_caches(short_code=short_code)

    return RedirectResponse(
        url=link.original_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.put("/{short_code}", response_model=LinkRead)
async def update_link(
    short_code: str,
    payload: LinkUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Link:
    link = await get_active_link_by_code(session, short_code)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found.",
        )

    try:
        ensure_user_can_manage_link(link, current_user)
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    old_original_url = link.original_url
    link.original_url = str(payload.original_url)
    await session.commit()
    await session.refresh(link)
    await invalidate_link_caches(
        short_code=short_code,
        original_urls=[old_original_url, link.original_url],
    )
    return link


@router.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    short_code: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    link = await get_active_link_by_code(session, short_code)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found.",
        )

    try:
        ensure_user_can_manage_link(link, current_user)
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    original_url = link.original_url
    await session.delete(link)
    await session.commit()
    await invalidate_link_caches(
        short_code=short_code,
        original_urls=[original_url],
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
