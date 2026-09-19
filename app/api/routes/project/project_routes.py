# app/api/routes/project/project_routes.py
from fastapi import APIRouter

from app.api.dependencies import ProjectServiceDep
from app.api.routes.project.project_schemas import (
    ProjectDetailResponse,
    ProjectSummaryResponse,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=PaginatedResponse[ProjectSummaryResponse])
async def list_projects(
    service: ProjectServiceDep,
    pagination: PaginationDep,
    q: str | None = None,
) -> PaginatedResponse[ProjectSummaryResponse]:
    items, total = await service.list_public(pagination, q=q)
    return PaginatedResponse.from_page(items, total=total, pagination=pagination)


@router.get("/{slug}", response_model=ProjectDetailResponse)
async def get_project(
    slug: str,
    service: ProjectServiceDep,
) -> ProjectDetailResponse:
    return await service.get_by_slug(slug)
