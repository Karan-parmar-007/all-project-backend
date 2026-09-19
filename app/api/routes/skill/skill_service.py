# app/api/routes/skill/skill_service.py
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from uuid import UUID

import uuid6
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes.project.model import ApProject, ApProjectStatus
from app.api.routes.skill.model import ApSkill, ApSkillCategory
from app.api.routes.skill.skill_schemas import (
    SkillBrief,
    SkillCategoryCreateRequest,
    SkillCategoryGroup,
    SkillCategoryResponse,
    SkillCategoryUpdateRequest,
    SkillListResponse,
)
from app.config import media_settings
from app.core.errors import ConflictError, MediaError, NotFoundError, ValidationError
from app.utils.garage import GarageStorage
from app.utils.media_urls import api_media_url

HOME_CATEGORY_LIMIT = 3


def _safe_filename(name: str | None) -> str:
    if not name:
        return "upload"
    name = unicodedata.normalize("NFKD", name)
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:200] or "upload"


class SkillService:
    def __init__(
        self,
        pg_session: AsyncSession,
        garage: GarageStorage | None = None,
    ) -> None:
        self.pg_session = pg_session
        self.garage = garage

    def _icon_url(self, key: str | None) -> str | None:
        if not key:
            return None
        return api_media_url(key)

    async def _skill_counts(self) -> dict[str, int]:
        """Count projects per skill name, excluding hidden projects."""
        from app.api.routes.project.project_constants import HIDDEN_STATUS_SLUG

        proj_stmt = (
            select(ApProject.tech_stack)
            .join(ApProjectStatus, ApProject.status_id == ApProjectStatus.id)
            .where(func.lower(ApProjectStatus.slug) != HIDDEN_STATUS_SLUG)
        )
        proj_rows = (await self.pg_session.execute(proj_stmt)).scalars().all()
        skill_counts: dict[str, int] = defaultdict(int)
        for stack in proj_rows:
            if isinstance(stack, list):
                for s in stack:
                    skill_counts[str(s).strip().lower()] += 1
        return skill_counts

    def _to_brief(
        self,
        skill: ApSkill,
        *,
        category_name: str | None,
        counts: dict[str, int],
    ) -> SkillBrief:
        return SkillBrief(
            id=skill.id,
            name=skill.name,
            sequence=skill.sequence,
            category_id=skill.category_id,
            category_name=category_name,
            project_count=counts.get(skill.name.strip().lower(), 0),
            show_in_about=skill.show_in_about,
            icon_key=skill.icon_key,
            icon_url=self._icon_url(skill.icon_key),
        )

    async def _assert_home_capacity(self, *, exclude_id: UUID | None = None) -> None:
        stmt = select(func.count()).select_from(ApSkillCategory).where(
            ApSkillCategory.show_on_home.is_(True)
        )
        if exclude_id is not None:
            stmt = stmt.where(ApSkillCategory.id != exclude_id)
        count = (await self.pg_session.execute(stmt)).scalar_one()
        if count >= HOME_CATEGORY_LIMIT:
            raise ValidationError(
                f"At most {HOME_CATEGORY_LIMIT} skill categories can appear on the home page"
            )

    async def _validate_and_read_icon(
        self, file: UploadFile
    ) -> tuple[str, bytes, str]:
        content = await file.read()
        if not content:
            raise MediaError("File is empty")
        content_type = (file.content_type or "").split(";")[0].strip().lower()
        if content_type not in media_settings.allowed_image_types:
            raise MediaError(
                f"Content type '{content_type}' is not an allowed image type"
            )
        if len(content) > media_settings.MEDIA_MAX_IMAGE_BYTES:
            raise MediaError(
                f"File exceeds maximum size of {media_settings.MEDIA_MAX_IMAGE_BYTES} bytes"
            )
        filename = _safe_filename(file.filename)
        key = f"apps/skills/{uuid6.uuid7()}/{filename}"
        return key, content, content_type

    async def list_skills(
        self, *, on_home: bool | None = None, in_about: bool | None = None
    ) -> SkillListResponse:
        counts = await self._skill_counts()

        cat_stmt = select(ApSkillCategory).order_by(ApSkillCategory.sequence.asc())
        if on_home is True:
            cat_stmt = cat_stmt.where(ApSkillCategory.show_on_home.is_(True))
        categories = (await self.pg_session.execute(cat_stmt)).scalars().all()
        if on_home is True:
            categories = categories[:HOME_CATEGORY_LIMIT]

        skill_stmt = select(ApSkill).order_by(ApSkill.sequence.asc())
        if in_about is True:
            skill_stmt = skill_stmt.where(ApSkill.show_in_about.is_(True))
        skills = (await self.pg_session.execute(skill_stmt)).scalars().all()

        cat_map = {c.id: c for c in categories}
        allowed_cat_ids = set(cat_map) if on_home is True else None

        all_skills: list[SkillBrief] = []
        grouped: dict[str, list[SkillBrief]] = defaultdict(list)

        for s in skills:
            if allowed_cat_ids is not None and s.category_id not in allowed_cat_ids:
                continue
            c_name = cat_map[s.category_id].name if s.category_id in cat_map else "Other"
            if on_home is True and s.category_id not in cat_map:
                continue
            brief = self._to_brief(
                s,
                category_name=c_name if s.category_id in cat_map else None,
                counts=counts,
            )
            all_skills.append(brief)
            grouped[c_name].append(brief)

        items: list[SkillCategoryGroup] = []
        for c in categories:
            items.append(
                SkillCategoryGroup(
                    id=c.id,
                    name=c.name,
                    sequence=c.sequence,
                    show_on_home=c.show_on_home,
                    skills=grouped.get(c.name, []),
                )
            )

        if on_home is not True and "Other" in grouped:
            items.append(
                SkillCategoryGroup(
                    id=None,
                    name="Other",
                    sequence=999,
                    show_on_home=False,
                    skills=grouped["Other"],
                )
            )

        return SkillListResponse(items=items, all_skills=all_skills)

    async def list_about_skills(self) -> list[SkillBrief]:
        counts = await self._skill_counts()
        stmt = (
            select(ApSkill)
            .options(selectinload(ApSkill.category))
            .where(ApSkill.show_in_about.is_(True))
            .order_by(ApSkill.sequence.asc())
        )
        skills = (await self.pg_session.execute(stmt)).scalars().all()
        return [
            self._to_brief(
                s,
                category_name=s.category.name if s.category else None,
                counts=counts,
            )
            for s in skills
        ]

    async def list_categories(
        self, *, on_home: bool | None = None
    ) -> list[SkillCategoryResponse]:
        grouped = await self.list_skills(on_home=on_home)
        return [
            SkillCategoryResponse(
                id=g.id,
                name=g.name,
                sequence=g.sequence,
                show_on_home=g.show_on_home,
                skills=g.skills,
            )
            for g in grouped.items
            if g.id is not None
        ]

    async def list_admin_skills(self) -> list[SkillBrief]:
        counts = await self._skill_counts()
        stmt = (
            select(ApSkill)
            .options(selectinload(ApSkill.category))
            .order_by(ApSkill.sequence.asc())
        )
        skills = (await self.pg_session.execute(stmt)).scalars().all()
        return [
            self._to_brief(
                s,
                category_name=s.category.name if s.category else None,
                counts=counts,
            )
            for s in skills
        ]

    async def create_category(
        self, data: SkillCategoryCreateRequest
    ) -> SkillCategoryResponse:
        existing = (
            await self.pg_session.execute(
                select(ApSkillCategory).where(ApSkillCategory.name == data.name)
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Skill category name already exists")
        sequence = data.sequence
        if sequence is None:
            max_seq = (
                await self.pg_session.execute(
                    select(func.max(ApSkillCategory.sequence))
                )
            ).scalar_one_or_none()
            sequence = (max_seq or 0) + 1
        if data.show_on_home:
            await self._assert_home_capacity()
        row = ApSkillCategory(
            name=data.name,
            sequence=sequence,
            show_on_home=data.show_on_home,
        )
        self.pg_session.add(row)
        await self.pg_session.commit()
        await self.pg_session.refresh(row)
        return SkillCategoryResponse(
            id=row.id,
            name=row.name,
            sequence=row.sequence,
            show_on_home=row.show_on_home,
            skills=[],
        )

    async def update_category(
        self, category_id: UUID, data: SkillCategoryUpdateRequest
    ) -> SkillCategoryResponse:
        row = (
            await self.pg_session.execute(
                select(ApSkillCategory)
                .options(selectinload(ApSkillCategory.skills))
                .where(ApSkillCategory.id == category_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Skill category not found")
        payload = data.model_dump(exclude_unset=True)
        if "name" in payload:
            clash = (
                await self.pg_session.execute(
                    select(ApSkillCategory).where(
                        ApSkillCategory.name == payload["name"],
                        ApSkillCategory.id != category_id,
                    )
                )
            ).scalar_one_or_none()
            if clash is not None:
                raise ConflictError("Skill category name already exists")
        if payload.get("show_on_home") is True and not row.show_on_home:
            await self._assert_home_capacity(exclude_id=category_id)
        for key, value in payload.items():
            setattr(row, key, value)
        await self.pg_session.commit()
        cats = await self.list_categories()
        match = next((c for c in cats if c.id == category_id), None)
        if match is None:
            raise NotFoundError("Skill category not found")
        return match

    async def delete_category(self, category_id: UUID) -> None:
        row = (
            await self.pg_session.execute(
                select(ApSkillCategory).where(ApSkillCategory.id == category_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Skill category not found")
        await self.pg_session.delete(row)
        await self.pg_session.commit()

    async def reorder_categories(self, ids: list[UUID]) -> list[SkillCategoryResponse]:
        rows = (await self.pg_session.execute(select(ApSkillCategory))).scalars().all()
        by_id = {r.id: r for r in rows}
        if set(ids) != set(by_id):
            raise ValidationError("Reorder must include every existing id exactly once")
        for index, item_id in enumerate(ids):
            by_id[item_id].sequence = index + 1
        await self.pg_session.commit()
        return await self.list_categories()

    async def create_skill(
        self,
        *,
        name: str,
        category_id: UUID | None,
        sequence: int | None,
        show_in_about: bool,
        icon: UploadFile | None,
    ) -> SkillBrief:
        existing = (
            await self.pg_session.execute(select(ApSkill).where(ApSkill.name == name))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Skill name already exists")
        if category_id is not None:
            cat = (
                await self.pg_session.execute(
                    select(ApSkillCategory).where(ApSkillCategory.id == category_id)
                )
            ).scalar_one_or_none()
            if cat is None:
                raise NotFoundError("Skill category not found")
        seq = sequence
        if seq is None:
            max_seq = (
                await self.pg_session.execute(select(func.max(ApSkill.sequence)))
            ).scalar_one_or_none()
            seq = (max_seq or 0) + 1

        icon_key = None
        if icon is not None and icon.filename:
            if self.garage is None:
                raise MediaError("Storage is not configured")
            icon_key, content, content_type = await self._validate_and_read_icon(icon)
            await self.garage.upload(icon_key, content, content_type)

        row = ApSkill(
            name=name,
            category_id=category_id,
            sequence=seq,
            show_in_about=show_in_about,
            icon_key=icon_key,
        )
        self.pg_session.add(row)
        try:
            await self.pg_session.commit()
            await self.pg_session.refresh(row)
        except Exception:
            await self.pg_session.rollback()
            if icon_key and self.garage is not None:
                await self.garage.delete(icon_key)
            raise
        return await self.get_skill(row.id)

    async def get_skill(self, skill_id: UUID) -> SkillBrief:
        counts = await self._skill_counts()
        row = (
            await self.pg_session.execute(
                select(ApSkill)
                .options(selectinload(ApSkill.category))
                .where(ApSkill.id == skill_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Skill not found")
        return self._to_brief(
            row,
            category_name=row.category.name if row.category else None,
            counts=counts,
        )

    async def update_skill(
        self,
        skill_id: UUID,
        *,
        name: str | None,
        category_id: UUID | None,
        sequence: int | None,
        show_in_about: bool | None,
        icon: UploadFile | None,
        category_id_set: bool = False,
    ) -> SkillBrief:
        row = (
            await self.pg_session.execute(
                select(ApSkill).where(ApSkill.id == skill_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Skill not found")
        if name is not None:
            clash = (
                await self.pg_session.execute(
                    select(ApSkill).where(ApSkill.name == name, ApSkill.id != skill_id)
                )
            ).scalar_one_or_none()
            if clash is not None:
                raise ConflictError("Skill name already exists")
            row.name = name
        if category_id_set:
            if category_id is not None:
                cat = (
                    await self.pg_session.execute(
                        select(ApSkillCategory).where(ApSkillCategory.id == category_id)
                    )
                ).scalar_one_or_none()
                if cat is None:
                    raise NotFoundError("Skill category not found")
            row.category_id = category_id
        if sequence is not None:
            row.sequence = sequence
        if show_in_about is not None:
            row.show_in_about = show_in_about

        old_icon = row.icon_key
        if icon is not None and icon.filename:
            if self.garage is None:
                raise MediaError("Storage is not configured")
            new_key, content, content_type = await self._validate_and_read_icon(icon)
            await self.garage.replace(
                old_key=old_icon,
                new_key=new_key,
                content=content,
                content_type=content_type,
            )
            row.icon_key = new_key

        await self.pg_session.commit()
        return await self.get_skill(skill_id)

    async def delete_skill(self, skill_id: UUID) -> None:
        row = (
            await self.pg_session.execute(select(ApSkill).where(ApSkill.id == skill_id))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Skill not found")
        icon_key = row.icon_key
        await self.pg_session.delete(row)
        await self.pg_session.commit()
        if icon_key and self.garage is not None:
            await self.garage.delete(icon_key)

    async def delete_skill_icon(self, skill_id: UUID) -> None:
        row = (
            await self.pg_session.execute(select(ApSkill).where(ApSkill.id == skill_id))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Skill not found")
        old_key = row.icon_key
        row.icon_key = None
        await self.pg_session.commit()
        if old_key and self.garage is not None:
            await self.garage.delete(old_key)

    async def reorder_skills(self, ids: list[UUID]) -> list[SkillBrief]:
        rows = (await self.pg_session.execute(select(ApSkill))).scalars().all()
        by_id = {r.id: r for r in rows}
        if set(ids) != set(by_id):
            raise ValidationError("Reorder must include every existing id exactly once")
        for index, item_id in enumerate(ids):
            by_id[item_id].sequence = index + 1
        await self.pg_session.commit()
        return await self.list_admin_skills()
