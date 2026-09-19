# app/api/routes/skill/skill_schemas.py
from __future__ import annotations

from uuid import UUID
from pydantic import Field

from app.api.schemas.common import CamelModel


class SkillBrief(CamelModel):
    id: UUID
    name: str
    sequence: int = 0
    category_id: UUID | None = None
    category_name: str | None = None
    project_count: int = 0
    show_in_about: bool = False
    icon_key: str | None = None
    icon_url: str | None = None


class SkillCategoryGroup(CamelModel):
    id: UUID | None = None
    name: str
    sequence: int = 0
    show_on_home: bool = False
    skills: list[SkillBrief] = Field(default_factory=list)


class SkillListResponse(CamelModel):
    items: list[SkillCategoryGroup]
    all_skills: list[SkillBrief] = Field(default_factory=list)


class SkillCategoryCreateRequest(CamelModel):
    name: str = Field(..., max_length=100)
    sequence: int | None = None
    show_on_home: bool = False


class SkillCategoryUpdateRequest(CamelModel):
    name: str | None = Field(default=None, max_length=100)
    sequence: int | None = None
    show_on_home: bool | None = None


class SkillCategoryResponse(CamelModel):
    id: UUID
    name: str
    sequence: int
    show_on_home: bool = False
    skills: list[SkillBrief] = Field(default_factory=list)


class SkillCategoryListResponse(CamelModel):
    items: list[SkillCategoryResponse]


class SkillResponse(SkillBrief):
    pass


class SkillItemsResponse(CamelModel):
    items: list[SkillBrief]
