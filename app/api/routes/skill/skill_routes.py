# app/api/routes/skill/skill_routes.py
from fastapi import APIRouter, Query

from app.api.dependencies import SkillServiceDep
from app.api.routes.skill.skill_schemas import SkillListResponse

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=SkillListResponse)
async def list_skills(
    service: SkillServiceDep,
    on_home: bool | None = Query(default=None),
    in_about: bool | None = Query(default=None),
) -> SkillListResponse:
    """Return skills grouped by category with project usage counts."""
    return await service.list_skills(on_home=on_home, in_about=in_about)
