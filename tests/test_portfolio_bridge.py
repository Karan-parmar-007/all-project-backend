# tests/test_portfolio_bridge.py
import pytest
import httpx


@pytest.mark.asyncio
async def test_portfolio_featured_endpoint(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/api/allprojects/portfolio/featured")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) <= 12
    # Verify featured projects from migration
    names = [item["name"] for item in data["items"]]
    assert "Whisper AI: AI-Powered Blogging Platform" in names
    assert "Ai Data Analyst" in names


@pytest.mark.asyncio
async def test_portfolio_projects_endpoint(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/api/allprojects/portfolio/projects")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) <= 50
    # Check non-featured projects
    names = [item["name"] for item in data["items"]]
    assert "Flipkart Scraper" in names


@pytest.mark.asyncio
async def test_public_projects_list_and_slug(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/api/allprojects/projects")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    slugs = {item["slug"] for item in data["items"]}
    assert "advance-maps-scraper" in slugs or len(data["items"]) > 0

    # Test single project by slug
    slug_resp = await app_client.get("/api/allprojects/projects/whisper-ai-ai-powered-blogging-platform")
    assert slug_resp.status_code == 200
    proj = slug_resp.json()
    assert proj["slug"] == "whisper-ai-ai-powered-blogging-platform"
    assert "status" in proj
    assert "requiredRoles" in proj or "required_roles" in proj
