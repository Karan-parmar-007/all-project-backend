# tests/test_health.py
import pytest
import httpx


@pytest.mark.asyncio
async def test_health_check(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/api/allprojects/health")
    assert response.status_code == 200
    data = response.json()
    assert data["postgres"] == "ok"
    assert data["garage"] == "ok"
