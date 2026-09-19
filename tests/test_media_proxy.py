# tests/test_media_proxy.py
from __future__ import annotations

from app.config import db_settings
from app.utils.html_sanitize import sanitize_project_html
from app.utils.media_urls import api_media_url, is_allowed_media_key


def test_api_media_url_uses_public_proxy() -> None:
    url = api_media_url("apps/covers/abc/cover.jpg")
    assert url is not None
    assert url.endswith("/api/allprojects/media/apps/covers/abc/cover.jpg")
    assert "3900" not in url


def test_rejects_unsafe_keys() -> None:
    assert is_allowed_media_key("apps/covers/x.jpg") is True
    assert is_allowed_media_key("../secret") is False
    assert is_allowed_media_key("etc/passwd") is False


def test_sanitize_strips_script() -> None:
    html = sanitize_project_html('<p>Hi</p><script>alert(1)</script><img src="https://x.test/a.png" alt="a">')
    assert "<script>" not in html
    assert "<p>Hi</p>" in html
    assert "https://x.test/a.png" in html


def test_sanitize_plain_text_becomes_paragraphs() -> None:
    html = sanitize_project_html("Hello\nWorld")
    assert "<p>Hello</p>" in html
    assert "<p>World</p>" in html
