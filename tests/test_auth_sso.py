# tests/test_auth_sso.py
"""Auth integration tests against a fake SSO (RSA key + JWKS + /auth/me) served
through httpx.MockTransport and injected via karan_sso's configure()."""
from __future__ import annotations

import secrets
import time
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from karan_sso import SsoSettings

from app.auth.dependencies import AuthenticatedDep
from app.auth.sso import configure_sso
from app.config import CorsSettings
from app.core.errors import register_exception_handlers

SSO_BASE = "http://sso.test/api"
ISSUER = "http://sso.test/api/auth"
SCRAPER = "/api/allprojects/apps/demo/advance-scraper"


class FakeSso:
    """Minimal SSO: JWKS, GET /auth/me (bearer), GET /auth/admin/roles."""

    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "test-key"
        self.me_mode = "ok"  # ok | revoked | down
        self.roles_mode = "ok"  # ok | down | forbidden
        self.me_user: dict = {"role_name": "user", "app_roles": {}}
        self.me_requests: list[httpx.Request] = []
        self.roles_requests: list[httpx.Request] = []

    def jwks(self) -> dict:
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
        jwk.update({"kid": self.kid, "alg": "RS256", "use": "sig"})
        return {"keys": [jwk]}

    def token(
        self,
        *,
        role: str = "user",
        roles: dict | None = None,
        exp_in: int = 900,
        key: rsa.RSAPrivateKey | None = None,
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "sub": "user-1",
            "user_id": "user-1",
            "email": "user@example.com",
            "name": "User One",
            "email_verified": True,
            "role": role,
            "roles": roles or {},
            "sid": "sess-1",
            "jti": secrets.token_hex(8),  # unique token → fresh live-check cache entry
            "iat": now,
            "exp": now + exp_in,
            "type": "access",
        }
        return jwt.encode(
            claims, key or self.key, algorithm="RS256", headers={"kid": self.kid}
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/auth/.well-known/jwks.json":
            return httpx.Response(200, json=self.jwks())
        if path == "/api/auth/me":
            self.me_requests.append(request)
            if self.me_mode == "down":
                raise httpx.ConnectError("SSO down", request=request)
            if self.me_mode == "revoked":
                return httpx.Response(401, json={"detail": "Session revoked"})
            return httpx.Response(
                200,
                json={
                    "id": "user-1",
                    "email": "user@example.com",
                    "name": "User One",
                    "email_verified": True,
                    **self.me_user,
                },
            )
        if path == "/api/auth/admin/roles":
            self.roles_requests.append(request)
            if self.roles_mode == "down":
                raise httpx.ConnectError("SSO down", request=request)
            if self.roles_mode == "forbidden":
                return httpx.Response(403, json={"detail": "Admin access required"})
            return httpx.Response(
                200,
                json={
                    "total_count": 2,
                    "roles": [{"id": "r1", "name": "owner"}, {"id": "r2", "name": "tester"}],
                },
            )
        return httpx.Response(404, json={"detail": "not found"})


class _FakePg:
    async def get_session(self):
        yield MagicMock()


@pytest.fixture
def fake_sso() -> AsyncIterator[FakeSso]:
    fake = FakeSso()
    configure_sso(
        SsoSettings(
            _env_file=None,
            SSO_BASE_URL=SSO_BASE,
            SSO_ISSUER=ISSUER,
            SSO_JWT_SECRET="",
            SSO_APP_ID="allprojects",
        ),
        http=lambda: httpx.AsyncClient(transport=httpx.MockTransport(fake.handler)),
    )
    yield fake
    configure_sso()  # back to the app's real settings


@pytest.fixture
async def client(fake_sso: FakeSso) -> AsyncIterator[httpx.AsyncClient]:
    from main import app

    previous = getattr(app.state, "postgres_session", None)
    app.state.postgres_session = _FakePg()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.state.postgres_session = previous


def _cookie_login(client: httpx.AsyncClient, token: str) -> str:
    csrf = secrets.token_urlsafe(16)
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf)
    return csrf


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# -- ordinary authenticated routes: local verification only -----------------


@pytest.fixture
async def plain_client(fake_sso: FakeSso) -> AsyncIterator[httpx.AsyncClient]:
    mini = FastAPI()
    register_exception_handlers(mini)

    @mini.get("/whoami")
    async def whoami(identity: AuthenticatedDep) -> dict:
        return {"user_id": identity.user_id, "email": identity.email, "live": identity.live}

    transport = httpx.ASGITransport(app=mini)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_authenticated_route_401_without_token(plain_client, fake_sso) -> None:
    assert (await plain_client.get("/whoami")).status_code == 401


async def test_authenticated_route_rejects_bad_tokens(plain_client, fake_sso) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = fake_sso.token(key=other_key)
    expired = fake_sso.token(exp_in=-120)
    assert (await plain_client.get("/whoami", headers=_bearer(forged))).status_code == 401
    assert (await plain_client.get("/whoami", headers=_bearer(expired))).status_code == 401


async def test_authenticated_route_200_without_sso_me_call(plain_client, fake_sso) -> None:
    token = fake_sso.token()
    plain_client.cookies.set("access_token", token)
    response = await plain_client.get("/whoami")
    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1", "email": "user@example.com", "live": False}
    assert fake_sso.me_requests == []  # local JWT verification only


# -- admin routes: live check -------------------------------------------------


async def test_admin_401_without_token(client, fake_sso) -> None:
    assert (await client.get("/api/allprojects/admin/sso-roles")).status_code == 401


async def test_admin_403_for_regular_user(client, fake_sso) -> None:
    _cookie_login(client, fake_sso.token(role="user"))
    response = await client.get("/api/allprojects/admin/sso-roles")
    assert response.status_code == 403
    assert fake_sso.roles_requests == []


async def test_admin_403_after_live_demotion(client, fake_sso) -> None:
    fake_sso.me_user = {"role_name": "user", "app_roles": {}}
    _cookie_login(client, fake_sso.token(role="super_admin"))  # stale token role
    assert (await client.get("/api/allprojects/admin/sso-roles")).status_code == 403


async def test_admin_401_when_session_revoked(client, fake_sso) -> None:
    fake_sso.me_mode = "revoked"
    _cookie_login(client, fake_sso.token(role="owner"))
    assert (await client.get("/api/allprojects/admin/sso-roles")).status_code == 401


async def test_admin_503_when_sso_down(client, fake_sso) -> None:
    fake_sso.me_mode = "down"
    _cookie_login(client, fake_sso.token(role="owner"))
    assert (await client.get("/api/allprojects/admin/sso-roles")).status_code == 503


async def test_admin_200_for_app_admin(client, fake_sso) -> None:
    fake_sso.me_user = {"role_name": "user", "app_roles": {"allprojects": ["admin"]}}
    _cookie_login(client, fake_sso.token(role="user", roles={"allprojects": ["admin"]}))
    response = await client.get("/api/allprojects/admin/sso-roles")
    assert response.status_code == 200


# -- sso-roles proxy ------------------------------------------------------------


async def test_sso_roles_proxy_sends_bearer_not_cookie(client, fake_sso) -> None:
    fake_sso.me_user = {"role_name": "super_admin", "app_roles": {}}
    token = fake_sso.token(role="super_admin")
    _cookie_login(client, token)
    response = await client.get("/api/allprojects/admin/sso-roles")
    assert response.status_code == 200
    assert response.json() == {
        "items": [{"id": "r1", "name": "owner"}, {"id": "r2", "name": "tester"}]
    }
    (upstream,) = fake_sso.roles_requests
    assert upstream.url == httpx.URL(f"{SSO_BASE}/auth/admin/roles")
    assert upstream.headers["authorization"] == f"Bearer {token}"
    assert "cookie" not in upstream.headers


async def test_sso_roles_proxy_503_when_sso_unreachable(client, fake_sso) -> None:
    fake_sso.me_user = {"role_name": "owner", "app_roles": {}}
    fake_sso.roles_mode = "down"
    _cookie_login(client, fake_sso.token(role="owner"))
    assert (await client.get("/api/allprojects/admin/sso-roles")).status_code == 503


async def test_sso_roles_proxy_passes_sso_403(client, fake_sso) -> None:
    fake_sso.me_user = {"role_name": "user", "app_roles": {"allprojects": ["admin"]}}
    fake_sso.roles_mode = "forbidden"
    _cookie_login(client, fake_sso.token(roles={"allprojects": ["admin"]}))
    assert (await client.get("/api/allprojects/admin/sso-roles")).status_code == 403


# -- live-app project gate: fail closed ------------------------------------------


def _gate_patches(required_roles: list[str]):
    project = SimpleNamespace(
        id=uuid4(), slug="demo", name="Demo", app_key="advance_scraper", status_id=uuid4()
    )
    status = SimpleNamespace(slug="live", name="Live", allows_access=True)
    return (
        patch("app.auth.project_gate._load_project_by_slug", AsyncMock(return_value=project)),
        patch("app.auth.project_gate._load_status", AsyncMock(return_value=status)),
        patch("app.auth.project_gate._load_roles", AsyncMock(return_value=required_roles)),
    )


async def _get_gate(client, required_roles: list[str]) -> httpx.Response:
    p1, p2, p3 = _gate_patches(required_roles)
    with p1, p2, p3:
        return await client.get(f"{SCRAPER}/locations/countries")


async def test_gate_401_without_token(client, fake_sso) -> None:
    assert (await _get_gate(client, [])).status_code == 401


async def test_gate_open_app_allows_signed_in_user(client, fake_sso) -> None:
    _cookie_login(client, fake_sso.token())
    assert (await _get_gate(client, [])).status_code == 200


async def test_gate_open_app_blocks_revoked_session(client, fake_sso) -> None:
    fake_sso.me_mode = "revoked"
    _cookie_login(client, fake_sso.token())
    assert (await _get_gate(client, [])).status_code == 401


async def test_gate_open_app_503_when_sso_down(client, fake_sso) -> None:
    fake_sso.me_mode = "down"
    _cookie_login(client, fake_sso.token())
    assert (await _get_gate(client, [])).status_code == 503


async def test_gate_role_app_uses_live_role(client, fake_sso) -> None:
    # Token still claims "tester" but SSO says the role was removed.
    fake_sso.me_user = {"role_name": "user", "app_roles": {}}
    _cookie_login(client, fake_sso.token(role="tester"))
    assert (await _get_gate(client, ["tester"])).status_code == 403


async def test_gate_role_app_allows_live_role(client, fake_sso) -> None:
    fake_sso.me_user = {"role_name": "tester", "app_roles": {}}
    _cookie_login(client, fake_sso.token(role="user"))
    assert (await _get_gate(client, ["tester"])).status_code == 200


async def test_gate_role_app_503_when_sso_down(client, fake_sso) -> None:
    fake_sso.me_mode = "down"
    _cookie_login(client, fake_sso.token(role="tester"))
    assert (await _get_gate(client, ["tester"])).status_code == 503


async def test_bootstrap_reports_live_access(client, fake_sso) -> None:
    fake_sso.me_user = {"role_name": "tester", "app_roles": {}}
    _cookie_login(client, fake_sso.token(role="user"))
    p1, p2, p3 = _gate_patches(["tester"])
    with p1, p2, p3:
        response = await client.get("/api/allprojects/apps/demo/bootstrap")
    assert response.status_code == 200
    assert response.json()["canAccess"] is True


async def test_bootstrap_revoked_session_is_anonymous(client, fake_sso) -> None:
    fake_sso.me_mode = "revoked"
    _cookie_login(client, fake_sso.token())
    p1, p2, p3 = _gate_patches([])
    with p1, p2, p3:
        response = await client.get("/api/allprojects/apps/demo/bootstrap")
    assert response.status_code == 200
    assert response.json()["canAccess"] is False


# -- CSRF ------------------------------------------------------------------------


async def test_csrf_403_without_header_on_cookie_mutation(client, fake_sso) -> None:
    _cookie_login(client, fake_sso.token())
    response = await client.post(f"{SCRAPER}/runs/stream", json={"search_term": "x"})
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token missing or invalid"
    assert fake_sso.me_requests == []  # rejected before auth


async def test_csrf_docs_referer_is_not_a_bypass(client, fake_sso) -> None:
    _cookie_login(client, fake_sso.token(role="owner"))
    response = await client.post(
        "/api/allprojects/admin/project-statuses",
        json={"name": "x"},
        headers={"Referer": "http://test/docs"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token missing or invalid"


async def test_csrf_header_passes_to_auth(client, fake_sso) -> None:
    csrf = _cookie_login(client, fake_sso.token(role="user"))
    response = await client.post(
        "/api/allprojects/admin/project-statuses",
        json={"name": "x"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


async def test_csrf_not_required_for_bearer_only(client, fake_sso) -> None:
    response = await client.post(
        "/api/allprojects/admin/project-statuses",
        json={"name": "x"},
        headers=_bearer(fake_sso.token(role="user")),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


# -- removed endpoints / config --------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/allprojects/auth/session"),
        ("POST", "/api/allprojects/auth/refresh"),
        ("POST", "/api/allprojects/auth/logout"),
        ("POST", "/api/auth/refresh"),
        ("POST", "/api/auth/logout"),
        ("GET", "/api/auth/session"),
    ],
)
async def test_auth_proxies_removed(client, method: str, path: str) -> None:
    response = await client.request(method, path)
    assert response.status_code in (404, 405)


def test_cors_drops_localhost_in_production() -> None:
    origins = "http://localhost:1576,https://app.karanparmar.in,http://127.0.0.1:5173"
    prod = CorsSettings(_env_file=None, ENVIRONMENT="production", CORS_ALLOWED_ORIGINS=origins)
    dev = CorsSettings(_env_file=None, ENVIRONMENT="development", CORS_ALLOWED_ORIGINS=origins)
    assert prod.allowed_origins == ["https://app.karanparmar.in"]
    assert "http://localhost:1576" in dev.allowed_origins
