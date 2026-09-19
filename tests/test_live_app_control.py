# tests/test_live_app_control.py
"""Unit tests for live-app gate, registry shutdown, and stream registry."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.auth.dependencies import SsoIdentity
from app.auth.project_gate import (
    _role_allowed,
    bootstrap_project_app,
    resolve_project_app_access,
)
from app.core.errors import AppOfflineError, ForbiddenError, NotFoundError
from app.live_apps import is_known_app_key, list_live_apps, shutdown_app
from app.live_apps.registry import register_runtime_shutdown
from app.api.routes.advance_scraper.service import _RunRegistry, run_registry


def _identity(*, role: str | None = "viewer") -> SsoIdentity:
    return SsoIdentity(
        user_id="user-1",
        email="user@example.com",
        is_owner=False,
        role_name=role,
        name="User",
    )


def test_advance_scraper_is_registered() -> None:
    assert is_known_app_key("advance_scraper")
    keys = {item["key"] for item in list_live_apps()}
    assert "advance_scraper" in keys


def test_role_allowed_empty_roles_means_any_authenticated() -> None:
    assert _role_allowed(_identity(role="anything"), []) is True
    assert _role_allowed(_identity(role=None), []) is True


def test_role_allowed_requires_membership() -> None:
    assert _role_allowed(_identity(role="owner"), ["Owner", "admin"]) is True
    assert _role_allowed(_identity(role="viewer"), ["owner"]) is False
    assert _role_allowed(_identity(role=None), ["owner"]) is False


def test_shutdown_app_invokes_runtime_hooks() -> None:
    calls: list[str] = []

    def hook() -> None:
        calls.append("hit")

    register_runtime_shutdown("advance_scraper", hook)
    shutdown_app("advance_scraper")
    assert "hit" in calls


@pytest.mark.asyncio
async def test_resolve_unlinked_project_not_found() -> None:
    session = AsyncMock()
    project = SimpleNamespace(id=uuid4(), slug="demo", name="Demo", app_key=None, status_id=uuid4())
    with patch("app.auth.project_gate._load_project_by_slug", AsyncMock(return_value=project)):
        with pytest.raises(NotFoundError):
            await resolve_project_app_access(
                session=session,
                identity=_identity(),
                project_slug="demo",
                expected_app_key="advance_scraper",
            )


@pytest.mark.asyncio
async def test_resolve_offline_status_raises_503_domain() -> None:
    session = AsyncMock()
    project = SimpleNamespace(
        id=uuid4(),
        slug="maps",
        name="Maps",
        app_key="advance_scraper",
        status_id=uuid4(),
    )
    status = SimpleNamespace(slug="offline", name="Offline", allows_access=False)
    with (
        patch("app.auth.project_gate._load_project_by_slug", AsyncMock(return_value=project)),
        patch("app.auth.project_gate._load_status", AsyncMock(return_value=status)),
        patch("app.auth.project_gate._load_roles", AsyncMock(return_value=[])),
    ):
        with pytest.raises(AppOfflineError) as exc:
            await resolve_project_app_access(
                session=session,
                identity=_identity(),
                project_slug="maps",
                expected_app_key="advance_scraper",
            )
        assert exc.value.code == "app_offline"


@pytest.mark.asyncio
async def test_resolve_wrong_role_forbidden() -> None:
    session = AsyncMock()
    project = SimpleNamespace(
        id=uuid4(),
        slug="maps",
        name="Maps",
        app_key="advance_scraper",
        status_id=uuid4(),
    )
    status = SimpleNamespace(slug="live", name="Live", allows_access=True)
    with (
        patch("app.auth.project_gate._load_project_by_slug", AsyncMock(return_value=project)),
        patch("app.auth.project_gate._load_status", AsyncMock(return_value=status)),
        patch("app.auth.project_gate._load_roles", AsyncMock(return_value=["owner"])),
    ):
        with pytest.raises(ForbiddenError):
            await resolve_project_app_access(
                session=session,
                identity=_identity(role="viewer"),
                project_slug="maps",
                expected_app_key="advance_scraper",
            )


@pytest.mark.asyncio
async def test_resolve_empty_roles_allows_any_authenticated() -> None:
    session = AsyncMock()
    project = SimpleNamespace(
        id=uuid4(),
        slug="maps",
        name="Maps",
        app_key="advance_scraper",
        status_id=uuid4(),
    )
    status = SimpleNamespace(slug="live", name="Live", allows_access=True)
    with (
        patch("app.auth.project_gate._load_project_by_slug", AsyncMock(return_value=project)),
        patch("app.auth.project_gate._load_status", AsyncMock(return_value=status)),
        patch("app.auth.project_gate._load_roles", AsyncMock(return_value=[])),
    ):
        access = await resolve_project_app_access(
            session=session,
            identity=_identity(role="viewer"),
            project_slug="maps",
            expected_app_key="advance_scraper",
        )
    assert access.app_key == "advance_scraper"
    assert access.project_slug == "maps"


@pytest.mark.asyncio
async def test_bootstrap_reports_offline_without_raising() -> None:
    session = AsyncMock()
    project = SimpleNamespace(
        id=uuid4(),
        slug="maps",
        name="Maps",
        app_key="advance_scraper",
        status_id=uuid4(),
    )
    status = SimpleNamespace(slug="maintenance", name="Maintenance", allows_access=False)
    with (
        patch("app.auth.project_gate._load_project_by_slug", AsyncMock(return_value=project)),
        patch("app.auth.project_gate._load_status", AsyncMock(return_value=status)),
        patch("app.auth.project_gate._load_roles", AsyncMock(return_value=[])),
    ):
        boot = await bootstrap_project_app(
            session=session,
            identity=_identity(),
            project_slug="maps",
        )
    assert boot.allows_access is False
    assert boot.can_access is False
    assert boot.live_url == "/apps/maps"


def test_run_registry_stop_all_signals_active_job() -> None:
    registry = _RunRegistry()
    job = SimpleNamespace(
        id="job-1",
        stop_event=MagicMock(),
        events=MagicMock(),
        running=True,
        finished=False,
    )
    registry._jobs["user-1"] = job  # type: ignore[attr-defined]
    registry.stop_all()
    job.stop_event.set.assert_called()
    assert job.events.put.call_count >= 2


def test_global_run_registry_wired_to_shutdown() -> None:
    # Import side-effect registers runtime shutdown for advance_scraper.
    assert run_registry is not None
    calls: list[int] = []
    original = run_registry.stop_all

    def wrapped() -> None:
        calls.append(1)
        original()

    register_runtime_shutdown("advance_scraper", wrapped)
    shutdown_app("advance_scraper")
    assert calls == [1]
