# app/utils/media_urls.py
from __future__ import annotations

from urllib.parse import quote

from app.config import media_settings

MEDIA_KEY_PREFIX = "apps/"


def is_allowed_media_key(key: str) -> bool:
    clean = key.lstrip("/")
    if not clean.startswith(MEDIA_KEY_PREFIX):
        return False
    if ".." in clean or clean.startswith("/") or "\\" in clean:
        return False
    return True


def api_media_url(key: str | None) -> str | None:
    """Browser-reachable URL that proxies Garage through this API."""
    if not key:
        return None
    clean = key.lstrip("/")
    if not is_allowed_media_key(clean):
        return None
    base = media_settings.PUBLIC_API_URL.rstrip("/")
    return f"{base}/api/allprojects/media/{quote(clean, safe='/')}"
