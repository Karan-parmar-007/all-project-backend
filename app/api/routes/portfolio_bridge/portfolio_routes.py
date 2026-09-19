# app/api/routes/portfolio_bridge/portfolio_routes.py
"""Public, unauthenticated endpoints for the portfolio site to fetch project cards."""
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db_dependencies import PGSessionDep
from app.api.routes.portfolio_bridge.portfolio_schemas import (
    PortfolioFeaturedResponse,
    PortfolioProjectCard,
    PortfolioProjectsResponse,
)
from app.api.routes.project.model import (
    ApProject,
    ApProjectRoleLink,
    ApProjectStatus,
    ApProjectTag,
    ApProjectTagLink,
)
from app.api.routes.project.project_constants import (
    MAX_FEATURED_PROJECTS,
    MAX_NON_FEATURED_PORTFOLIO,
)
from app.api.routes.skill.skill_schemas import SkillItemsResponse, SkillListResponse
from app.api.routes.skill.skill_service import SkillService
from app.utils.media_urls import api_media_url

router = APIRouter(prefix="/portfolio", tags=["portfolio-bridge"])


async def _to_card(session: AsyncSession, p: ApProject) -> PortfolioProjectCard:
    tag_rows = (
        await session.execute(
            select(ApProjectTag.name)
            .join(ApProjectTagLink, ApProjectTag.id == ApProjectTagLink.tag_id)
            .where(ApProjectTagLink.project_id == p.id)
        )
    ).scalars().all()

    role_rows = (
        await session.execute(
            select(ApProjectRoleLink.role_name)
            .where(ApProjectRoleLink.project_id == p.id)
            .order_by(ApProjectRoleLink.role_name.asc())
        )
    ).scalars().all()

    status = (
        await session.execute(
            select(ApProjectStatus).where(ApProjectStatus.id == p.status_id)
        )
    ).scalar_one()

    cover_url = api_media_url(p.cover_image_key)

    return PortfolioProjectCard(
        id=p.id,
        name=p.name,
        slug=p.slug,
        short_description=p.short_description,
        status=status.slug,
        live_url=p.live_url,
        github_url=p.github_url,
        cover_image_key=p.cover_image_key,
        cover_image_url=cover_url,
        tech_stack=p.tech_stack or [],
        tags=list(tag_rows),
        required_roles=list(role_rows),
    )


@router.get("/featured", response_model=PortfolioFeaturedResponse)
async def get_featured_projects(session: PGSessionDep) -> PortfolioFeaturedResponse:
    rows = (
        await session.execute(
            select(ApProject)
            .join(ApProjectStatus, ApProject.status_id == ApProjectStatus.id)
            .where(
                ApProject.is_featured == True,  # noqa: E712
                ApProjectStatus.show_in_list == True,  # noqa: E712
            )
            .order_by(ApProject.sequence.asc())
            .limit(MAX_FEATURED_PROJECTS)
        )
    ).scalars().all()

    items = [await _to_card(session, p) for p in rows]
    return PortfolioFeaturedResponse(items=items)


@router.get("/projects", response_model=PortfolioProjectsResponse)
async def get_non_featured_projects(
    session: PGSessionDep,
) -> PortfolioProjectsResponse:
    rows = (
        await session.execute(
            select(ApProject)
            .join(ApProjectStatus, ApProject.status_id == ApProjectStatus.id)
            .where(
                ApProject.is_featured == False,  # noqa: E712
                ApProjectStatus.show_in_list == True,  # noqa: E712
            )
            .order_by(ApProject.sequence.asc())
            .limit(MAX_NON_FEATURED_PORTFOLIO)
        )
    ).scalars().all()

    items = [await _to_card(session, p) for p in rows]
    return PortfolioProjectsResponse(items=items)


@router.get("/skill-categories", response_model=SkillListResponse)
async def get_home_skill_categories(session: PGSessionDep) -> SkillListResponse:
    service = SkillService(pg_session=session)
    return await service.list_skills(on_home=True)


@router.get("/skills", response_model=SkillListResponse)
async def get_all_skill_categories(session: PGSessionDep) -> SkillListResponse:
    service = SkillService(pg_session=session)
    return await service.list_skills()


@router.get("/about-skills", response_model=SkillItemsResponse)
async def get_about_skills(session: PGSessionDep) -> SkillItemsResponse:
    service = SkillService(pg_session=session)
    return SkillItemsResponse(items=await service.list_about_skills())
