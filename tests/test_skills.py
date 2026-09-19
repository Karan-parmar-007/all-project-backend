# tests/test_skills.py
import pytest
import httpx


@pytest.mark.asyncio
async def test_list_skills_grouped(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/api/allprojects/skills")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "allSkills" in data or "all_skills" in data
    assert len(data["items"]) >= 3  # Programming Languages, Frontend, Backend
    
    cat_names = [group["name"] for group in data["items"]]
    assert "Programming Langunages" in cat_names or "Programming Languages" in cat_names
    assert "Backend" in cat_names
    assert "Frontend" in cat_names

    # Check project counts
    all_s = data.get("allSkills") or data.get("all_skills")
    python_skill = next((s for s in all_s if s["name"] == "Python"), None)
    assert python_skill is not None
    assert python_skill["projectCount"] > 0 or python_skill.get("project_count", 0) > 0
