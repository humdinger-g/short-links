from collections.abc import AsyncIterator

import pytest

import app.db.session as session_module


class DummySessionContext:
    def __init__(self, session: object) -> None:
        self.session = session

    async def __aenter__(self) -> object:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class DummySessionFactory:
    def __init__(self, session: object) -> None:
        self.session = session

    def __call__(self) -> DummySessionContext:
        return DummySessionContext(self.session)


@pytest.mark.asyncio
async def test_get_db_session_yields_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_session = object()
    monkeypatch.setattr(
        session_module,
        "SessionFactory",
        DummySessionFactory(sentinel_session),
    )

    session_iterator = session_module.get_db_session()

    assert await anext(session_iterator) is sentinel_session

    with pytest.raises(StopAsyncIteration):
        await anext(session_iterator)
