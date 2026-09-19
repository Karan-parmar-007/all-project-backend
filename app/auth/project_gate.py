# app/auth/project_gate.py
"""Central access control for code-backed live apps."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db_dependencies import PGSessionDep
from app.api.routes.project.model import (
    ApProject,
    ApProjectRoleLink,
    ApProjectStatus,
)
from app.api.schemas.common import CamelModel
from app.auth.dependencies import SsoIdentity, get_authenticated_identity
from app.core.errors import AppOfflineError, ForbiddenError, NotFoundError
from app.live_apps import is_known_app_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectAppAccess:
    project_id: UUID
    project_slug: str
    project_name: str
    app_key: str
    status_slug: str
    status_allows_access: bool
    required_roles: list[str]
    identity: SsoIdentity


class AppBootstrapResponse(CamelModel):
    project_id: UUID
    project_slug: str
    project_name: str
    app_key: str
    status_slug: str
    status_name: str
    allows_access: bool
    required_roles: list[str]
    can_access: bool
    live_url: str


async def _load_project_by_slug(session: AsyncSession, slug: str) -> ApProject:
    project = (
        await session.execute(select(ApProject).where(ApProject.slug == slug))
    ).scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def _load_status(session: AsyncSession, status_id: UUID) -> ApProjectStatus:
    status = (
        await session.execute(
            select(ApProjectStatus).where(ApProjectStatus.id == status_id)
        )
    ).scalar_one_or_none()
    if status is None:
        raise NotFoundError("Project status not found")
    return status


async def _load_roles(session: AsyncSession, project_id: UUID) -> list[str]:
    rows = (
        await session.execute(
            select(ApProjectRoleLink.role_name).where(
                ApProjectRoleLink.project_id == project_id
            )
        )
    ).scalars().all()
    return [str(r) for r in rows]


def _role_allowed(identity: SsoIdentity, required_roles: list[str]) -> bool:
    if not required_roles:
        return True
    current = (identity.role_name or "").strip().lower()
    allowed = {r.strip().lower() for r in required_roles if r and str(r).strip()}
    return bool(current) and current in allowed


async def resolve_project_app_access(
    *,
    session: AsyncSession,
    identity: SsoIdentity,
    project_slug: str,
    expected_app_key: str | None = None,
    enforce: bool = True,
) -> ProjectAppAccess:
    project = await _load_project_by_slug(session, project_slug)
    if not project.app_key or not is_known_app_key(project.app_key):
        raise NotFoundError("No live app is linked to this project")
    if expected_app_key and project.app_key != expected_app_key:
        raise NotFoundError("This project is not linked to the requested app")

    status = await _load_status(session, project.status_id)
    roles = await _load_roles(session, project.id)
    access = ProjectAppAccess(
        project_id=project.id,
        project_slug=project.slug,
        project_name=project.name,
        app_key=project.app_key,
        status_slug=status.slug,
        status_allows_access=status.allows_access,
        required_roles=roles,
        identity=identity,
    )

    if not enforce:
        return access

    if not status.allows_access:
        raise AppOfflineError(
            f"“{project.name}” is currently unavailable ({status.name})."
        )
    if not _role_allowed(identity, roles):
        logger.warning(
            "Live app role denied user=%s role=%s project=%s required=%s",
            identity.email,
            identity.role_name,
            project.slug,
            roles,
        )
        raise ForbiddenError("Your role cannot access this app")
    return access


def require_project_app(expected_app_key: str):
    """Dependency factory: gate every endpoint of a code-backed live app."""

    async def _dependency(
        project_slug: str,
        request: Request,
        session: PGSessionDep,
    ) -> ProjectAppAccess:
        identity = await get_authenticated_identity(request)
        return await resolve_project_app_access(
            session=session,
            identity=identity,
            project_slug=project_slug,
            expected_app_key=expected_app_key,
            enforce=True,
        )

    return _dependency


async def bootstrap_project_app(
    *,
    session: AsyncSession,
    identity: SsoIdentity | None,
    project_slug: str,
) -> AppBootstrapResponse:
    """Public bootstrap for /apps/:slug — does not raise on offline/role denial."""
    project = await _load_project_by_slug(session, project_slug)
    if not project.app_key or not is_known_app_key(project.app_key):
        raise NotFoundError("No live app is linked to this project")
    status = await _load_status(session, project.status_id)
    roles = await _load_roles(session, project.id)
    can_access = False
    if identity is not None and status.allows_access:
        can_access = _role_allowed(identity, roles)
    return AppBootstrapResponse(
        project_id=project.id,
        project_slug=project.slug,
        project_name=project.name,
        app_key=project.app_key,
        status_slug=status.slug,
        status_name=status.name,
        allows_access=status.allows_access,
        required_roles=roles,
        can_access=can_access,
        live_url=f"/apps/{project.slug}",
    )
