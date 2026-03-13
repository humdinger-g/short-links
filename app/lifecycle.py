import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.cache import get_redis_client
from app.db.session import SessionFactory, engine
from app.links.cache import invalidate_link_caches
from app.links.cleanup import delete_expired_links, delete_unused_links
from app.settings import get_settings


logger = logging.getLogger(__name__)


async def cleanup_links_worker() -> None:
    settings = get_settings()
    interval = settings.expired_links_cleanup_interval_seconds
    while True:
        try:
            async with SessionFactory() as session:
                expired_links = await delete_expired_links(session)
            for link in expired_links:
                await invalidate_link_caches(
                    short_code=link.short_code,
                    original_urls=[link.original_url],
                )

            async with SessionFactory() as session:
                unused_links = await delete_unused_links(session, settings.unused_link_days)
            for link in unused_links:
                await invalidate_link_caches(
                    short_code=link.short_code,
                    original_urls=[link.original_url],
                )
        except Exception:
            logger.exception("Links cleanup failed.")

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    cleanup_task = asyncio.create_task(cleanup_links_worker())
    yield
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup_task
    await get_redis_client().aclose()
    await engine.dispose()
