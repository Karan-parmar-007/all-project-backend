# app/auth/dependencies.py
"""Thin adapters over the shared karan_sso SDK (see karan_sso/fastapi.py).

- Ordinary authenticated routes: local JWT verification, no SSO call.
- Admin/owner/role routes: live SSO check (30 s cache); SSO outage → 503.
- Admin = global owner/super_admin OR app role `admin` in SSO_APP_ID.
"""
from __future__ import annotations

from karan_sso import SsoIdentity
from karan_sso.fastapi import (
    AdminDep,
    IdentityDep,
    LiveIdentityDep,
    OptionalIdentityDep,
    OwnerDep,
    get_identity,
    get_live_identity,
    get_optional_identity,
    get_sso,
    require_admin,
    require_owner,
    require_role,
)

# Existing name: locally verified identity (401 when missing/invalid).
get_authenticated_identity = get_identity
AuthenticatedDep = IdentityDep

__all__ = [
    "AdminDep",
    "AuthenticatedDep",
    "IdentityDep",
    "LiveIdentityDep",
    "OptionalIdentityDep",
    "OwnerDep",
    "SsoIdentity",
    "get_authenticated_identity",
    "get_identity",
    "get_live_identity",
    "get_optional_identity",
    "get_sso",
    "require_admin",
    "require_owner",
    "require_role",
]
