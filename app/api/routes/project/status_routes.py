# app/api/routes/project/status_routes.py
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ProjectServiceDep
from app.api.routes.project.project_schemas import (
    StatusBrief,
    StatusCreateRequest,
    StatusListResponse,
    StatusUpdateRequest,
)
from app.auth.dependencies import require_admin

public_router = APIRouter(prefix="/project-statuses", tags=["project-statuses"])
admin_router = APIRouter(
    prefix="/admin/project-statuses",
    tags=["admin:project-statuses"],
    dependencies=[Depends(require_admin)],
)


@public_router.get("", response_model=StatusListResponse)
async def list_public_statuses(service: ProjectServiceDep) -> StatusListResponse:
    return StatusListResponse(items=await service.list_statuses(public_only=True))


@admin_router.get("", response_model=StatusListResponse)
async def list_admin_statuses(service: ProjectServiceDep) -> StatusListResponse:
    return StatusListResponse(items=await service.list_statuses(public_only=False))


@admin_router.post("", response_model=StatusBrief, status_code=status.HTTP_201_CREATED)
async def create_status(
    body: StatusCreateRequest,
    service: ProjectServiceDep,
) -> StatusBrief:
    return await service.create_status(body)


@admin_router.put("/{status_id}", response_model=StatusBrief)
async def update_status(
    status_id: UUID,
    body: StatusUpdateRequest,
    service: ProjectServiceDep,
) -> StatusBrief:
    return await service.update_status(status_id, body)


@admin_router.delete("/{status_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_status(status_id: UUID, service: ProjectServiceDep) -> None:
    await service.delete_status(status_id)
