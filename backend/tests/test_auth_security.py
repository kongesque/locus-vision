"""Security regression tests for authentication and browser API access."""

import httpx
import pytest
import pytest_asyncio

from config import settings
from database import init_db
from main import app
from routers.auth import _login_attempts


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "locusvision.db"))
    _login_attempts.clear()
    await init_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def create_admin_session(client: httpx.AsyncClient) -> dict[str, str]:
    register = await client.post(
        "/api/auth/register",
        json={"name": "Beta Admin", "email": "admin@example.com", "password": "beta-pass-123"},
    )
    assert register.status_code == 201

    login = await client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "beta-pass-123"},
    )
    assert login.status_code == 200
    return login.json()


@pytest.mark.asyncio
async def test_product_api_requires_auth_and_accepts_access_cookie(client):
    unauthenticated = await client.get("/api/cameras")
    assert unauthenticated.status_code == 401

    tokens = await create_admin_session(client)
    client.cookies.set("access_token", tokens["access_token"])

    authenticated = await client.get("/api/cameras")
    assert authenticated.status_code == 200
    assert authenticated.json() == []


@pytest.mark.asyncio
async def test_logout_revokes_refresh_session(client):
    tokens = await create_admin_session(client)

    rotated = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert rotated.status_code == 200
    rotated_tokens = rotated.json()

    logged_out = await client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {rotated_tokens['access_token']}"},
    )
    assert logged_out.status_code == 200

    revoked = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": rotated_tokens["refresh_token"]},
    )
    assert revoked.status_code == 401


@pytest.mark.asyncio
async def test_cors_rejects_untrusted_origins(client):
    trusted = await client.options(
        "/api/cameras",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert trusted.status_code == 200
    assert trusted.headers["access-control-allow-origin"] == "http://localhost:3000"

    untrusted = await client.options(
        "/api/cameras",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert untrusted.status_code == 400
    assert "access-control-allow-origin" not in untrusted.headers
