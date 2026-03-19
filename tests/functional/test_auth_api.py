import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login_flow(client: AsyncClient) -> None:
    register_response = await client.post(
        "/auth/register",
        json={"email": "USER@example.com", "password": "password123"},
    )

    assert register_response.status_code == 201
    assert register_response.json()["email"] == "user@example.com"

    login_response = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert login_response.status_code == 200
    body = login_response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    payload = {"email": "user@example.com", "password": "password123"}

    first_response = await client.post("/auth/register", json=payload)
    second_response = await client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )

    response = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
