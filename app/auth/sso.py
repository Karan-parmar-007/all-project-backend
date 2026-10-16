# app/auth/sso.py
"""Configure the shared karan_sso SDK, plus the few server-to-server SSO calls
this app makes (always with the user's access token as a bearer — never the
browser's Cookie header)."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from karan_sso import SsoSettings, SsoUnavailableError
from karan_sso.fastapi import SsoAuth, configure
from karan_sso.verifier import HttpClientFactory

from app.config import auth_settings

logger = logging.getLogger(__name__)

sso_settings: SsoSettings = auth_settings.sso_settings()

_http_factory: HttpClientFactory | None = None


def configure_sso(
    settings: SsoSettings | None = None,
    http: HttpClientFactory | None = None,
) -> SsoAuth:
    """Install the default SDK instance used by the auth dependencies.

    `http` (tests) replaces the HTTP client for the SDK and for this module.
    """
    global _http_factory
    _http_factory = http
    return configure(settings or sso_settings, http)


def _client(settings: SsoSettings) -> httpx.AsyncClient:
    if _http_factory is not None:
        return _http_factory()
    return httpx.AsyncClient(timeout=settings.SSO_HTTP_TIMEOUT_SECONDS)


class SsoUpstreamError(Exception):
    """SSO answered with an error status we pass through (401/403)."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def sso_get(
    sso: SsoAuth,
    path: str,
    *,
    access_token: str,
) -> Any:
    """GET {SSO_BASE_URL}{path} as the user. SsoUnavailableError on outage."""
    settings = sso.settings
    url = f"{settings.SSO_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        async with _client(settings) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("SSO GET %s unreachable: %s", path, exc)
        raise SsoUnavailableError("SSO unreachable") from exc

    if response.status_code in (401, 403):
        try:
            body = response.json()
            detail = body.get("detail") or body.get("message") or "Forbidden"
        except (ValueError, AttributeError):
            detail = "Forbidden"
        raise SsoUpstreamError(response.status_code, str(detail))
    if response.status_code != 200:
        logger.warning("SSO GET %s returned %s", path, response.status_code)
        raise SsoUnavailableError(f"SSO returned {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise SsoUnavailableError("SSO returned invalid JSON") from exc
