# tests/test_project_gate.py
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_bootstrap_unknown_project(app_client: AsyncClient) -> None:
    response = await app_client.get("/api/allprojects/apps/does-not-exist/bootstrap")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scraper_requires_auth(app_client: AsyncClient) -> None:
    response = await app_client.get(
        "/api/allprojects/apps/any-slug/advance-scraper/quota"
    )
    assert response.status_code == 401
