# app/api/routes/project/project_schemas.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.api.schemas.common import CamelModel


class TagBrief(CamelModel):
    id: UUID
    name: str


class TagCreateRequest(CamelModel):
    name: str = Field(..., max_length=50)


class TagListResponse(CamelModel):
    items: list[TagBrief]


class StatusBrief(CamelModel):
    id: UUID
    name: str
    slug: str
    sequence: int = 0
    show_in_list: bool = True
    allows_access: bool = False


class StatusCreateRequest(CamelModel):
    name: str = Field(..., min_length=1, max_length=80)
    show_in_list: bool = True
    allows_access: bool = False


class StatusUpdateRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    show_in_list: bool | None = None
    allows_access: bool | None = None
    sequence: int | None = None


class StatusListResponse(CamelModel):
    items: list[StatusBrief]


class LiveAppBrief(CamelModel):
    key: str
    name: str
    description: str


class LiveAppListResponse(CamelModel):
    items: list[LiveAppBrief]


class ProjectSummaryResponse(CamelModel):
    id: UUID
    name: str
    slug: str
    short_description: str
    status: StatusBrief
    is_featured: bool
    sequence: int
    live_url: str | None = None
    app_key: str | None = None
    github_url: str | None = None
    cover_image_key: str | None = None
    cover_image_url: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    tags: list[TagBrief] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    created_at: datetime


class ProjectDetailResponse(ProjectSummaryResponse):
    long_description: str
    updated_at: datetime


class ProjectListResponse(CamelModel):
    items: list[ProjectSummaryResponse]


class ProjectFeaturedRequest(CamelModel):
    is_featured: bool


class ProjectStatusRequest(CamelModel):
    status_id: UUID
