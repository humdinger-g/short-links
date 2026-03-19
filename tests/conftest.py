from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.cache as cache_module
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.storage.pop(key, None)

    async def aclose(self) -> None:
        return None


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    cache_module.get_redis_client.cache_clear()
    redis = FakeRedis()
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: redis)
    return redis


@pytest_asyncio.fixture
async def session_maker(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_path = tmp_path / "test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}", future=True)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield maker
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    session_maker: async_sessionmaker[AsyncSession],
    fake_redis: FakeRedis,
) -> AsyncIterator[AsyncClient]:
    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def make_auth_headers(
    client: AsyncClient,
) -> Callable[[str, str], Awaitable[dict[str, str]]]:
    async def _make(
        email: str = "user@example.com",
        password: str = "password123",
    ) -> dict[str, str]:
        register_response = await client.post(
            "/auth/register",
            json={"email": email, "password": password},
        )
        assert register_response.status_code == 201

        login_response = await client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make
