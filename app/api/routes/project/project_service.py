# app/api/routes/project/project_service.py
from __future__ import annotations

import re
import unicodedata
from uuid import UUID

import uuid6
from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.project.model import (
    ApProject,
    ApProjectRoleLink,
    ApProjectStatus,
    ApProjectTag,
    ApProjectTagLink,
)
from app.api.routes.project.project_constants import MAX_FEATURED_PROJECTS
from app.api.routes.project.project_schemas import (
    ProjectDetailResponse,
    ProjectSummaryResponse,
    StatusBrief,
    StatusCreateRequest,
    StatusUpdateRequest,
    TagBrief,
)
from app.api.schemas.pagination import PaginationParams
from app.config import media_settings
from app.core.errors import ConflictError, MediaError, NotFoundError, ValidationError
from app.core.slug import unique_slug
from app.utils.garage import GarageStorage
from app.utils.html_sanitize import sanitize_project_html
from app.utils.media_urls import api_media_url


def _safe_filename(name: str | None) -> str:
    if not name:
        return "upload"
    name = unicodedata.normalize("NFKD", name)
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:200] or "upload"


class ProjectService:
    def __init__(self, pg_session: AsyncSession, garage: GarageStorage) -> None:
        self.pg_session = pg_session
        self.garage = garage

    # ── helpers ──────────────────────────────────────────────────────────

    async def _get_tags(self, project_id: UUID) -> list[TagBrief]:
        stmt = (
            select(ApProjectTag)
            .join(ApProjectTagLink, ApProjectTag.id == ApProjectTagLink.tag_id)
            .where(ApProjectTagLink.project_id == project_id)
        )
        tags = (await self.pg_session.execute(stmt)).scalars().all()
        return [TagBrief(id=t.id, name=t.name) for t in tags]

    async def _get_roles(self, project_id: UUID) -> list[str]:
        rows = (
            await self.pg_session.execute(
                select(ApProjectRoleLink.role_name)
                .where(ApProjectRoleLink.project_id == project_id)
                .order_by(ApProjectRoleLink.role_name.asc())
            )
        ).scalars().all()
        return [str(r) for r in rows]

    async def _get_status(self, status_id: UUID) -> ApProjectStatus:
        row = (
            await self.pg_session.execute(
                select(ApProjectStatus).where(ApProjectStatus.id == status_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Status not found")
        return row

    def _status_brief(self, status: ApProjectStatus) -> StatusBrief:
        return StatusBrief(
            id=status.id,
            name=status.name,
            slug=status.slug,
            sequence=status.sequence,
            show_in_list=status.show_in_list,
            allows_access=status.allows_access,
        )

    def _get_cover_url(self, key: str | None) -> str | None:
        if not key:
            return None
        return api_media_url(key)

    @staticmethod
    def _effective_live_url(project: ApProject) -> str | None:
        if project.app_key:
            return f"/apps/{project.slug}"
        return project.live_url

    async def _assert_app_key_available(
        self, app_key: str | None, *, exclude_id: UUID | None = None
    ) -> None:
        if not app_key:
            return
        from app.live_apps import is_known_app_key

        if not is_known_app_key(app_key):
            raise ValidationError(f"Unknown live app key '{app_key}'")
        stmt = select(ApProject).where(ApProject.app_key == app_key)
        if exclude_id is not None:
            stmt = stmt.where(ApProject.id != exclude_id)
        clash = (await self.pg_session.execute(stmt)).scalar_one_or_none()
        if clash is not None:
            raise ConflictError(
                f"Live app '{app_key}' is already linked to another project"
            )

    async def _set_tags(self, project_id: UUID, tag_ids: list[UUID]) -> None:
        await self.pg_session.execute(
            delete(ApProjectTagLink).where(ApProjectTagLink.project_id == project_id)
        )
        for tid in tag_ids:
            tag = (
                await self.pg_session.execute(
                    select(ApProjectTag).where(ApProjectTag.id == tid)
                )
            ).scalar_one_or_none()
            if tag is None:
                raise NotFoundError(f"Tag {tid} not found")
            self.pg_session.add(ApProjectTagLink(project_id=project_id, tag_id=tid))

    async def _set_roles(self, project_id: UUID, role_names: list[str]) -> None:
        await self.pg_session.execute(
            delete(ApProjectRoleLink).where(ApProjectRoleLink.project_id == project_id)
        )
        seen: set[str] = set()
        for raw in role_names:
            name = raw.strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            self.pg_session.add(
                ApProjectRoleLink(project_id=project_id, role_name=name)
            )

    async def _to_summary(self, p: ApProject) -> ProjectSummaryResponse:
        status = await self._get_status(p.status_id)
        tags = await self._get_tags(p.id)
        roles = await self._get_roles(p.id)
        return ProjectSummaryResponse(
            id=p.id,
            name=p.name,
            slug=p.slug,
            short_description=p.short_description,
            status=self._status_brief(status),
            is_featured=p.is_featured,
            sequence=p.sequence,
            live_url=self._effective_live_url(p),
            app_key=p.app_key,
            github_url=p.github_url,
            cover_image_key=p.cover_image_key,
            cover_image_url=self._get_cover_url(p.cover_image_key),
            tech_stack=p.tech_stack or [],
            tags=tags,
            required_roles=roles,
            created_at=p.created_at,
        )

    async def _to_detail(self, p: ApProject) -> ProjectDetailResponse:
        summary = await self._to_summary(p)
        return ProjectDetailResponse(
            **summary.model_dump(),
            long_description=p.long_description,
            updated_at=p.updated_at,
        )

    async def _validate_and_upload_cover(
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
        key = f"apps/covers/{uuid6.uuid7()}/{filename}"
        return key, content, content_type

    # ── statuses ─────────────────────────────────────────────────────────

    async def list_statuses(self, *, public_only: bool = False) -> list[StatusBrief]:
        stmt = select(ApProjectStatus).order_by(
            ApProjectStatus.sequence.asc(), ApProjectStatus.name.asc()
        )
        if public_only:
            stmt = stmt.where(ApProjectStatus.show_in_list.is_(True))
        rows = (await self.pg_session.execute(stmt)).scalars().all()
        return [self._status_brief(r) for r in rows]

    async def create_status(self, body: StatusCreateRequest) -> StatusBrief:
        name = body.name.strip()
        if not name:
            raise ValidationError("Status name is required")
        slug = await unique_slug(self.pg_session, ApProjectStatus, name)
        clash = (
            await self.pg_session.execute(
                select(ApProjectStatus).where(
                    func.lower(ApProjectStatus.name) == name.lower()
                )
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise ConflictError("Status name already exists")
        max_seq = (
            await self.pg_session.execute(select(func.max(ApProjectStatus.sequence)))
        ).scalar_one_or_none()
        row = ApProjectStatus(
            name=name,
            slug=slug,
            sequence=(max_seq or 0) + 1,
            show_in_list=body.show_in_list,
            allows_access=body.allows_access,
        )
        self.pg_session.add(row)
        await self.pg_session.commit()
        await self.pg_session.refresh(row)
        return self._status_brief(row)

    async def update_status(
        self, status_id: UUID, body: StatusUpdateRequest
    ) -> StatusBrief:
        row = await self._get_status(status_id)
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise ValidationError("Status name is required")
            clash = (
                await self.pg_session.execute(
                    select(ApProjectStatus).where(
                        func.lower(ApProjectStatus.name) == name.lower(),
                        ApProjectStatus.id != status_id,
                    )
                )
            ).scalar_one_or_none()
            if clash is not None:
                raise ConflictError("Status name already exists")
            row.name = name
            row.slug = await unique_slug(
                self.pg_session, ApProjectStatus, name, exclude_id=status_id
            )
        if body.show_in_list is not None:
            row.show_in_list = body.show_in_list
        access_changed_off = (
            body.allows_access is not None
            and body.allows_access is False
            and row.allows_access is True
        )
        if body.allows_access is not None:
            row.allows_access = body.allows_access
        if body.sequence is not None:
            row.sequence = body.sequence
        await self.pg_session.commit()
        await self.pg_session.refresh(row)
        if access_changed_off:
            await self._shutdown_apps_for_status(status_id)
        return self._status_brief(row)

    async def delete_status(self, status_id: UUID) -> None:
        row = await self._get_status(status_id)
        in_use = (
            await self.pg_session.execute(
                select(func.count()).where(ApProject.status_id == status_id)
            )
        ).scalar_one()
        if in_use:
            raise ConflictError(
                f"Cannot delete status “{row.name}” — {in_use} project(s) still use it"
            )
        await self.pg_session.delete(row)
        await self.pg_session.commit()

    # ── public reads ─────────────────────────────────────────────────────

    async def list_public(
        self, pagination: PaginationParams, *, q: str | None = None
    ) -> tuple[list[ProjectSummaryResponse], int]:
        base = (
            select(ApProject)
            .join(ApProjectStatus, ApProject.status_id == ApProjectStatus.id)
            .where(ApProjectStatus.show_in_list.is_(True))
        )
        if q:
            base = base.where(ApProject.name.ilike(f"%{q}%"))

        total = (
            await self.pg_session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()

        rows = (
            await self.pg_session.execute(
                base.order_by(ApProject.sequence.asc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).scalars().all()

        items = [await self._to_summary(p) for p in rows]
        return items, total

    async def get_by_slug(self, slug: str) -> ProjectDetailResponse:
        project = (
            await self.pg_session.execute(
                select(ApProject).where(ApProject.slug == slug)
            )
        ).scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")
        return await self._to_detail(project)

    # ── admin reads ──────────────────────────────────────────────────────

    async def admin_list(
        self, pagination: PaginationParams, *, q: str | None = None
    ) -> tuple[list[ProjectDetailResponse], int]:
        base = select(ApProject)
        if q:
            base = base.where(ApProject.name.ilike(f"%{q}%"))

        total = (
            await self.pg_session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()

        rows = (
            await self.pg_session.execute(
                base.order_by(ApProject.sequence.asc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).scalars().all()

        items = [await self._to_detail(p) for p in rows]
        return items, total

    async def admin_get(self, project_id: UUID) -> ProjectDetailResponse:
        project = (
            await self.pg_session.execute(
                select(ApProject).where(ApProject.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")
        return await self._to_detail(project)

    # ── mutations ────────────────────────────────────────────────────────

    async def create_project(
        self,
        *,
        name: str,
        short_description: str,
        long_description: str,
        status_id: UUID,
        slug: str | None = None,
        is_featured: bool = False,
        live_url: str | None = None,
        app_key: str | None = None,
        github_url: str | None = None,
        tech_stack: list[str] | None = None,
        tag_ids: list[UUID] | None = None,
        role_names: list[str] | None = None,
        sequence: int | None = None,
        cover_image: UploadFile | None = None,
    ) -> ProjectDetailResponse:
        errors: list[str] = []
        await self._get_status(status_id)
        normalized_app_key = (app_key or "").strip() or None
        await self._assert_app_key_available(normalized_app_key)

        clash = (
            await self.pg_session.execute(
                select(ApProject).where(ApProject.name == name)
            )
        ).scalar_one_or_none()
        if clash is not None:
            errors.append("Project name already exists")

        if slug:
            slug_clash = (
                await self.pg_session.execute(
                    select(ApProject).where(ApProject.slug == slug)
                )
            ).scalar_one_or_none()
            if slug_clash is not None:
                errors.append("Project slug already exists")
            final_slug = slug
        else:
            final_slug = await unique_slug(self.pg_session, ApProject, name)

        if is_featured:
            count = (
                await self.pg_session.execute(
                    select(func.count()).where(ApProject.is_featured == True)  # noqa: E712
                )
            ).scalar_one()
            if count >= MAX_FEATURED_PROJECTS:
                errors.append(
                    f"Maximum {MAX_FEATURED_PROJECTS} featured projects reached"
                )

        if errors:
            raise ValidationError("; ".join(errors))

        seq = sequence
        if seq is None:
            max_seq = (
                await self.pg_session.execute(select(func.max(ApProject.sequence)))
            ).scalar_one_or_none()
            seq = (max_seq or 0) + 1

        cover_key = None
        if cover_image is not None and cover_image.filename:
            cover_key, content, content_type = await self._validate_and_upload_cover(
                cover_image
            )
            await self.garage.upload(cover_key, content, content_type)

        project = ApProject(
            name=name,
            slug=final_slug,
            short_description=short_description,
            long_description=sanitize_project_html(long_description),
            status_id=status_id,
            is_featured=is_featured,
            live_url=None if normalized_app_key else (live_url or None),
            app_key=normalized_app_key,
            github_url=github_url or None,
            tech_stack=tech_stack or [],
            sequence=seq,
            cover_image_key=cover_key,
        )
        self.pg_session.add(project)
        try:
            await self.pg_session.flush()
            if tag_ids:
                await self._set_tags(project.id, tag_ids)
            await self._set_roles(project.id, role_names or [])
            await self.pg_session.commit()
        except Exception:
            await self.pg_session.rollback()
            if cover_key:
                await self.garage.delete(cover_key)
            raise

        return await self.admin_get(project.id)

    async def update_project(
        self,
        project_id: UUID,
        *,
        fields: dict,
        tag_ids: list[UUID] | None,
        role_names: list[str] | None,
        cover_image: UploadFile | None,
    ) -> ProjectDetailResponse:
        project = (
            await self.pg_session.execute(
                select(ApProject).where(ApProject.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")

        old_app_key = project.app_key
        old_status_id = project.status_id
        old_roles = await self._get_roles(project_id)

        if "app_key" in fields:
            raw_key = fields["app_key"]
            normalized = (str(raw_key).strip() if raw_key else "") or None
            fields["app_key"] = normalized
            await self._assert_app_key_available(normalized, exclude_id=project_id)
            if normalized:
                # Code-backed apps use derived /apps/{slug} URLs.
                fields["live_url"] = None

        errors: list[str] = []

        if "status_id" in fields:
            await self._get_status(fields["status_id"])

        if "name" in fields and fields["name"] != project.name:
            clash = (
                await self.pg_session.execute(
                    select(ApProject).where(
                        ApProject.name == fields["name"],
                        ApProject.id != project_id,
                    )
                )
            ).scalar_one_or_none()
            if clash is not None:
                errors.append("Project name already exists")

        if "slug" in fields and fields["slug"] and fields["slug"] != project.slug:
            clash = (
                await self.pg_session.execute(
                    select(ApProject).where(
                        ApProject.slug == fields["slug"],
                        ApProject.id != project_id,
                    )
                )
            ).scalar_one_or_none()
            if clash is not None:
                errors.append("Project slug already exists")

        if "is_featured" in fields and fields["is_featured"] and not project.is_featured:
            count = (
                await self.pg_session.execute(
                    select(func.count()).where(
                        ApProject.is_featured == True,  # noqa: E712
                        ApProject.id != project_id,
                    )
                )
            ).scalar_one()
            if count >= MAX_FEATURED_PROJECTS:
                errors.append(
                    f"Maximum {MAX_FEATURED_PROJECTS} featured projects reached"
                )

        if errors:
            raise ValidationError("; ".join(errors))

        if "name" in fields and "slug" not in fields:
            fields["slug"] = await unique_slug(
                self.pg_session, ApProject, fields["name"], exclude_id=project_id
            )

        if "long_description" in fields and fields["long_description"] is not None:
            fields["long_description"] = sanitize_project_html(
                fields["long_description"]
            )

        for key, value in fields.items():
            setattr(project, key, value)

        if cover_image is not None and cover_image.filename:
            new_key, content, content_type = await self._validate_and_upload_cover(
                cover_image
            )
            old_key = project.cover_image_key
            await self.garage.replace(
                old_key=old_key,
                new_key=new_key,
                content=content,
                content_type=content_type,
            )
            project.cover_image_key = new_key

        if tag_ids is not None:
            await self._set_tags(project_id, tag_ids)
        if role_names is not None:
            await self._set_roles(project_id, role_names)
        await self.pg_session.commit()

        await self._maybe_shutdown_live_app(
            old_app_key=old_app_key,
            new_app_key=project.app_key,
            old_status_id=old_status_id,
            new_status_id=project.status_id,
            old_roles=old_roles,
            new_roles=(
                role_names
                if role_names is not None
                else await self._get_roles(project_id)
            ),
        )

        return await self.admin_get(project_id)

    async def _shutdown_apps_for_status(self, status_id: UUID) -> None:
        """Stop live-app runtimes for every project currently on this status."""
        from app.live_apps import shutdown_app

        keys = (
            await self.pg_session.execute(
                select(ApProject.app_key).where(
                    ApProject.status_id == status_id,
                    ApProject.app_key.is_not(None),
                )
            )
        ).scalars().all()
        for key in {str(k) for k in keys if k}:
            shutdown_app(key)

    async def _maybe_shutdown_live_app(
        self,
        *,
        old_app_key: str | None,
        new_app_key: str | None,
        old_status_id: UUID,
        new_status_id: UUID,
        old_roles: list[str],
        new_roles: list[str],
    ) -> None:
        from app.live_apps import shutdown_app

        keys_to_stop: set[str] = set()
        if old_app_key and old_app_key != new_app_key:
            keys_to_stop.add(old_app_key)
        if new_app_key:
            if old_status_id != new_status_id:
                new_status = await self._get_status(new_status_id)
                if not new_status.allows_access:
                    keys_to_stop.add(new_app_key)
            old_norm = sorted(r.lower() for r in old_roles)
            new_norm = sorted(r.lower() for r in (new_roles or []))
            if old_norm != new_norm:
                keys_to_stop.add(new_app_key)
        for key in keys_to_stop:
            shutdown_app(key)

    async def delete_project(self, project_id: UUID) -> None:
        project = (
            await self.pg_session.execute(
                select(ApProject).where(ApProject.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")

        cover_key = project.cover_image_key
        old_app_key = project.app_key
        await self.pg_session.delete(project)
        await self.pg_session.commit()
        if old_app_key:
            from app.live_apps import shutdown_app

            shutdown_app(old_app_key)
        if cover_key:
            await self.garage.delete(cover_key)

    async def delete_cover(self, project_id: UUID) -> None:
        project = (
            await self.pg_session.execute(
                select(ApProject).where(ApProject.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")
        old_key = project.cover_image_key
        if old_key:
            await self.garage.delete(old_key)
            project.cover_image_key = None
            await self.pg_session.commit()

    async def set_featured(
        self, project_id: UUID, is_featured: bool
    ) -> ProjectDetailResponse:
        project = (
            await self.pg_session.execute(
                select(ApProject).where(ApProject.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")

        if is_featured and not project.is_featured:
            count = (
                await self.pg_session.execute(
                    select(func.count()).where(
                        ApProject.is_featured == True,  # noqa: E712
                        ApProject.id != project_id,
                    )
                )
            ).scalar_one()
            if count >= MAX_FEATURED_PROJECTS:
                raise ValidationError(
                    f"Maximum {MAX_FEATURED_PROJECTS} featured projects reached"
                )

        project.is_featured = is_featured
        await self.pg_session.commit()
        return await self.admin_get(project_id)

    async def set_status(
        self, project_id: UUID, status_id: UUID
    ) -> ProjectDetailResponse:
        new_status = await self._get_status(status_id)
        project = (
            await self.pg_session.execute(
                select(ApProject).where(ApProject.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project not found")
        old_status_id = project.status_id
        old_app_key = project.app_key
        project.status_id = status_id
        await self.pg_session.commit()
        if old_status_id != status_id and old_app_key and not new_status.allows_access:
            from app.live_apps import shutdown_app

            shutdown_app(old_app_key)
        return await self.admin_get(project_id)

    async def reorder(self, ids: list[UUID]) -> list[ProjectSummaryResponse]:
        rows = (await self.pg_session.execute(select(ApProject))).scalars().all()
        by_id = {r.id: r for r in rows}
        if set(ids) != set(by_id):
            raise ValidationError("Reorder must include every existing id exactly once")
        for index, item_id in enumerate(ids):
            by_id[item_id].sequence = index + 1
        await self.pg_session.commit()
        loaded = (
            await self.pg_session.execute(
                select(ApProject).order_by(ApProject.sequence.asc())
            )
        ).scalars().all()
        return [await self._to_summary(p) for p in loaded]

    # ── tag management ───────────────────────────────────────────────────

    async def list_tags(self) -> list[TagBrief]:
        rows = (
            await self.pg_session.execute(
                select(ApProjectTag).order_by(ApProjectTag.name.asc())
            )
        ).scalars().all()
        return [TagBrief(id=t.id, name=t.name) for t in rows]

    async def create_tag(self, name: str) -> TagBrief:
        existing = (
            await self.pg_session.execute(
                select(ApProjectTag).where(ApProjectTag.name == name.strip().lower())
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Tag already exists")
        tag = ApProjectTag(name=name.strip().lower())
        self.pg_session.add(tag)
        await self.pg_session.commit()
        await self.pg_session.refresh(tag)
        return TagBrief(id=tag.id, name=tag.name)

    async def delete_tag(self, tag_id: UUID) -> None:
        tag = (
            await self.pg_session.execute(
                select(ApProjectTag).where(ApProjectTag.id == tag_id)
            )
        ).scalar_one_or_none()
        if tag is None:
            raise NotFoundError("Tag not found")
        await self.pg_session.delete(tag)
        await self.pg_session.commit()
