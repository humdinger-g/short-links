import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI

import app.lifecycle as lifecycle_module
from app.settings import get_settings


class DummySessionContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class DummySessionFactory:
    def __call__(self) -> DummySessionContext:
        return DummySessionContext()


class DummyTask:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def __await__(self):
        async def _done() -> None:
            return None

        return _done().__await__()


@pytest.mark.asyncio
async def test_cleanup_links_worker_invalidates_expired_and_unused_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "expired_links_cleanup_interval_seconds", 1)
    monkeypatch.setattr(settings, "unused_link_days", 30)
    monkeypatch.setattr(lifecycle_module, "SessionFactory", DummySessionFactory())
    invalidate_mock = AsyncMock()
    monkeypatch.setattr(lifecycle_module, "invalidate_link_caches", invalidate_mock)

    async def fake_delete_expired_links(session):
        return [SimpleNamespace(short_code="expired", original_url="https://e")]

    async def fake_delete_unused_links(session, unused_link_days):
        assert unused_link_days == 30
        return [SimpleNamespace(short_code="unused", original_url="https://u")]

    async def stop_after_one_iteration(interval: int) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr(lifecycle_module, "delete_expired_links", fake_delete_expired_links)
    monkeypatch.setattr(lifecycle_module, "delete_unused_links", fake_delete_unused_links)
    monkeypatch.setattr(lifecycle_module.asyncio, "sleep", stop_after_one_iteration)

    with pytest.raises(asyncio.CancelledError):
        await lifecycle_module.cleanup_links_worker()

    assert invalidate_mock.await_count == 2


@pytest.mark.asyncio
async def test_cleanup_links_worker_logs_failures_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "expired_links_cleanup_interval_seconds", 1)
    monkeypatch.setattr(lifecycle_module, "SessionFactory", DummySessionFactory())
    logger_mock = Mock()
    monkeypatch.setattr(lifecycle_module, "logger", logger_mock)

    async def failing_delete_expired_links(session):
        raise RuntimeError("boom")

    async def stop_after_one_iteration(interval: int) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr(
        lifecycle_module,
        "delete_expired_links",
        failing_delete_expired_links,
    )
    monkeypatch.setattr(lifecycle_module.asyncio, "sleep", stop_after_one_iteration)

    with pytest.raises(asyncio.CancelledError):
        await lifecycle_module.cleanup_links_worker()

    logger_mock.exception.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_cancels_worker_and_closes_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = DummyTask()
    redis_client = SimpleNamespace(aclose=AsyncMock())
    engine = SimpleNamespace(dispose=AsyncMock())

    def fake_create_task(coro):
        coro.close()
        return task

    monkeypatch.setattr(lifecycle_module.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(lifecycle_module, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(lifecycle_module, "engine", engine)

    async with lifecycle_module.lifespan(FastAPI()):
        pass

    assert task.cancelled is True
    redis_client.aclose.assert_awaited_once()
    engine.dispose.assert_awaited_once()
