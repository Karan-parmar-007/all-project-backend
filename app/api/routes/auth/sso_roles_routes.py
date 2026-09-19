# app/api/routes/auth/sso_roles_routes.py
"""Proxy SSO roles list for all_projects admins (owner + super_admin)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import require_admin
from app.auth.sso_client import cookie_header_from_request, proxy_sso
from app.core.errors import UnauthorizedError

router = APIRouter(
    prefix="/admin",
    tags=["admin:sso-roles"],
    dependencies=[Depends(require_admin)],
)


@router.get("/sso-roles")
async def list_sso_roles(request: Request) -> JSONResponse:
    cookie_header = request.headers.get("cookie") or cookie_header_from_request(
        dict(request.cookies)
    )
    try:
        upstream = await proxy_sso(
            "GET",
            "/auth/admin/roles",
            cookie_header=cookie_header,
        )
    except UnauthorizedError as exc:
        return JSONResponse(status_code=401, content={"detail": exc.message})

    try:
        body = upstream.json()
    except ValueError:
        body = {"detail": upstream.text or "Failed to load roles"}

    if upstream.status_code >= 400:
        return JSONResponse(
            status_code=upstream.status_code,
            content={"detail": body.get("detail") or body.get("message") or "Failed"},
        )

    roles = body.get("roles") or []
    items = [
        {
            "id": str(r.get("id")),
            "name": str(r.get("name")),
        }
        for r in roles
        if isinstance(r, dict) and r.get("name")
    ]
    return JSONResponse(status_code=200, content={"items": items})
