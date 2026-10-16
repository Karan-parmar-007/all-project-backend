"""SSO roles list for all_projects admins (role pickers for live-app gating).

Server-to-server: calls SSO with the admin's own access token as a bearer
(SSO checks the role again). The browser's Cookie header is never forwarded.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from karan_sso import SsoUnavailableError

from app.auth.dependencies import AdminDep, get_sso
from app.auth.sso import SsoUpstreamError, sso_get

router = APIRouter(prefix="/admin", tags=["admin:sso-roles"])


@router.get("/sso-roles")
async def list_sso_roles(request: Request, _admin: AdminDep) -> dict:
    sso = get_sso()
    token = sso.token_from_request(request)
    if not token:  # AdminDep already verified one; defensive only
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        body = await sso_get(sso, "/auth/admin/roles", access_token=token)
    except SsoUpstreamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except SsoUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable, try again shortly",
        ) from exc

    roles = body.get("roles") if isinstance(body, dict) else None
    items = [
        {"id": str(r.get("id")), "name": str(r.get("name"))}
        for r in roles or []
        if isinstance(r, dict) and r.get("name")
    ]
    return {"items": items}
