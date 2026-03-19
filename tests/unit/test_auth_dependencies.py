from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_optional_user
from app.auth.security import create_access_token


@pytest.mark.asyncio
async def test_get_current_user_requires_credentials(db_session: AsyncSession) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None, session=db_session)

    assert exc_info.value.detail == "Authentication is required."


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(db_session: AsyncSession) -> None:
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="bad-token",
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials, session=db_session)

    assert exc_info.value.detail == "Token has invalid format."


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_user(db_session: AsyncSession) -> None:
    token = create_access_token(uuid4())
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials, session=db_session)

    assert exc_info.value.detail == "User not found."


@pytest.mark.asyncio
async def test_get_optional_user_returns_none_without_credentials(
    db_session: AsyncSession,
) -> None:
    assert await get_optional_user(credentials=None, session=db_session) is None
