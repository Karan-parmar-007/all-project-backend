# app/api/routes/project/admin_project_routes.py
import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.dependencies import ProjectServiceDep
from app.api.routes.project.project_schemas import (
    LiveAppBrief,
    LiveAppListResponse,
    ProjectDetailResponse,
    ProjectFeaturedRequest,
    ProjectListResponse,
    ProjectStatusRequest,
    TagBrief,
    TagCreateRequest,
    TagListResponse,
)
from app.api.schemas.common import ReorderRequest
from app.api.schemas.pagination import PaginatedResponse, PaginationDep
from app.auth.dependencies import require_admin
from app.core.errors import ValidationError
from app.live_apps import list_live_apps

router = APIRouter(
    prefix="/admin/projects",
    tags=["admin:projects"],
    dependencies=[Depends(require_admin)],
)


def _parse_tag_ids(raw: str | None) -> list[UUID] | None:
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("tag_ids must be a JSON array of UUIDs") from exc
    if not isinstance(data, list):
        raise ValidationError("tag_ids must be a JSON array of UUIDs")
    try:
        return [UUID(str(x)) for x in data]
    except ValueError as exc:
        raise ValidationError("tag_ids contains an invalid UUID") from exc


def _parse_tech_stack(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("tech_stack must be a JSON array of strings") from exc
    if not isinstance(data, list):
        raise ValidationError("tech_stack must be a JSON array of strings")
    return [str(x) for x in data]


def _parse_role_names(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("role_names must be a JSON array of strings") from exc
    if not isinstance(data, list):
        raise ValidationError("role_names must be a JSON array of strings")
    return [str(x) for x in data]


@router.get("", response_model=PaginatedResponse[ProjectDetailResponse])
async def admin_list_projects(
    service: ProjectServiceDep,
    pagination: PaginationDep,
    q: str | None = None,
) -> PaginatedResponse[ProjectDetailResponse]:
    items, total = await service.admin_list(pagination, q=q)
    return PaginatedResponse.from_page(items, total=total, pagination=pagination)


@router.patch("/reorder", response_model=ProjectListResponse)
async def reorder_projects(
    body: ReorderRequest,
    service: ProjectServiceDep,
) -> ProjectListResponse:
    items = await service.reorder(body.ids)
    return ProjectListResponse(items=items)


@router.get("/tags/all", response_model=TagListResponse)
async def list_tags(service: ProjectServiceDep) -> TagListResponse:
    tags = await service.list_tags()
    return TagListResponse(items=tags)


@router.get("/live-apps", response_model=LiveAppListResponse)
async def admin_list_live_apps() -> LiveAppListResponse:
    return LiveAppListResponse(
        items=[LiveAppBrief(**item) for item in list_live_apps()]
    )


@router.post("/tags", response_model=TagBrief, status_code=status.HTTP_201_CREATED)
async def create_tag(body: TagCreateRequest, service: ProjectServiceDep) -> TagBrief:
    return await service.create_tag(body.name)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: UUID, service: ProjectServiceDep) -> None:
    await service.delete_tag(tag_id)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def admin_get_project(
    project_id: UUID,
    service: ProjectServiceDep,
) -> ProjectDetailResponse:
    return await service.admin_get(project_id)


@router.post(
    "", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED
)
async def create_project(
    service: ProjectServiceDep,
    name: str = Form(...),
    short_description: str = Form(...),
    long_description: str = Form(default=""),
    status_id: UUID = Form(...),
    slug: str | None = Form(default=None),
    is_featured: bool = Form(default=False),
    live_url: str | None = Form(default=None),
    app_key: str | None = Form(default=None),
    github_url: str | None = Form(default=None),
    tech_stack: str | None = Form(default=None),
    tag_ids: str | None = Form(default="[]"),
    role_names: str | None = Form(default="[]"),
    sequence: int | None = Form(default=None),
    cover_image: UploadFile | None = File(default=None),
) -> ProjectDetailResponse:
    return await service.create_project(
        name=name,
        short_description=short_description,
        long_description=long_description,
        status_id=status_id,
        slug=slug,
        is_featured=is_featured,
        live_url=live_url or None,
        app_key=app_key or None,
        github_url=github_url or None,
        tech_stack=_parse_tech_stack(tech_stack),
        tag_ids=_parse_tag_ids(tag_ids) or [],
        role_names=_parse_role_names(role_names) or [],
        sequence=sequence,
        cover_image=cover_image,
    )


@router.put("/{project_id}", response_model=ProjectDetailResponse)
async def update_project(
    project_id: UUID,
    service: ProjectServiceDep,
    name: str | None = Form(default=None),
    slug: str | None = Form(default=None),
    short_description: str | None = Form(default=None),
    long_description: str | None = Form(default=None),
    status_id: UUID | None = Form(default=None),
    is_featured: bool | None = Form(default=None),
    live_url: str | None = Form(default=None),
    app_key: str | None = Form(default=None),
    github_url: str | None = Form(default=None),
    tech_stack: str | None = Form(default=None),
    tag_ids: str | None = Form(default=None),
    role_names: str | None = Form(default=None),
    sequence: int | None = Form(default=None),
    cover_image: UploadFile | None = File(default=None),
) -> ProjectDetailResponse:
    fields: dict = {}
    if name is not None:
        fields["name"] = name
    if slug is not None:
        fields["slug"] = slug
    if short_description is not None:
        fields["short_description"] = short_description
    if long_description is not None:
        fields["long_description"] = long_description
    if status_id is not None:
        fields["status_id"] = status_id
    if is_featured is not None:
        fields["is_featured"] = is_featured
    # Always apply when present (including empty string → clear)
    if live_url is not None:
        fields["live_url"] = live_url.strip() or None
    if app_key is not None:
        fields["app_key"] = app_key.strip() or None
    if github_url is not None:
        fields["github_url"] = github_url.strip() or None
    if tech_stack is not None:
        fields["tech_stack"] = _parse_tech_stack(tech_stack)
    if sequence is not None:
        fields["sequence"] = sequence

    return await service.update_project(
        project_id,
        fields=fields,
        tag_ids=_parse_tag_ids(tag_ids),
        role_names=_parse_role_names(role_names),
        cover_image=cover_image,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID, service: ProjectServiceDep) -> None:
    await service.delete_project(project_id)


@router.delete("/{project_id}/cover", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cover(project_id: UUID, service: ProjectServiceDep) -> None:
    await service.delete_cover(project_id)


@router.patch("/{project_id}/featured", response_model=ProjectDetailResponse)
async def set_featured(
    project_id: UUID,
    body: ProjectFeaturedRequest,
    service: ProjectServiceDep,
) -> ProjectDetailResponse:
    return await service.set_featured(project_id, body.is_featured)


@router.patch("/{project_id}/status", response_model=ProjectDetailResponse)
async def set_status(
    project_id: UUID,
    body: ProjectStatusRequest,
    service: ProjectServiceDep,
) -> ProjectDetailResponse:
    return await service.set_status(project_id, body.status_id)
