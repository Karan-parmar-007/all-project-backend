# tests/test_auth_admin.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import secrets
from jose import jwt

from app.auth.cookies import ACCESS_TOKEN_COOKIE, CSRF_TOKEN_COOKIE
from app.config import auth_settings


def _mint_access_token(*, email: str, user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "type": "access",
            "user_id": user_id,
            "email": email,
            "exp": now + timedelta(hours=1),
        },
        auth_settings.SSO_JWT_SECRET,
        algorithm=auth_settings.SSO_JWT_ALGORITHM,
    )


def _cookies(email: str, user_id: str) -> dict[str, str]:
    return {
        ACCESS_TOKEN_COOKIE: _mint_access_token(email=email, user_id=user_id),
        CSRF_TOKEN_COOKIE: secrets.token_urlsafe(16),
    }


@pytest.mark.asyncio
async def test_session_unauthenticated(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/api/allprojects/auth/session")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["is_admin"] is False
    assert body["name"] is None


@pytest.mark.asyncio
async def test_session_super_admin_is_admin(app_client: httpx.AsyncClient) -> None:
    with patch(
        "app.auth.dependencies.fetch_sso_me",
        new=AsyncMock(
            return_value={
                "id": "sa-1",
                "email": "sa@example.com",
                "role_name": "super_admin",
                "name": "Super Admin",
            }
        ),
    ):
        app_client.cookies.update(_cookies("sa@example.com", "sa-1"))
        response = await app_client.get("/api/allprojects/auth/session")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["is_admin"] is True
    assert body["is_owner"] is False
    assert body["name"] == "Super Admin"


@pytest.mark.asyncio
async def test_admin_projects_403_for_user(app_client: httpx.AsyncClient) -> None:
    with patch(
        "app.auth.dependencies.fetch_sso_me",
        new=AsyncMock(
            return_value={
                "id": "u-1",
                "email": "user@example.com",
                "role_name": "user",
                "name": "Regular User",
            }
        ),
    ):
        app_client.cookies.update(_cookies("user@example.com", "u-1"))
        response = await app_client.get("/api/allprojects/admin/projects")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_projects_401_without_cookie(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/api/allprojects/admin/projects")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_proxies_set_cookie(app_client: httpx.AsyncClient) -> None:
    upstream = httpx.Response(
        200,
        json={"access_token_expires_in": 900, "message": "Token refreshed successfully"},
        headers=[("set-cookie", "access_token=new-token; Path=/; HttpOnly")],
    )
    with patch("app.api.routes.auth.auth_routes.proxy_sso", new=AsyncMock(return_value=upstream)):
        response = await app_client.post("/api/allprojects/auth/refresh")
    assert response.status_code == 200
    assert "access_token=" in response.headers.get("set-cookie", "")
