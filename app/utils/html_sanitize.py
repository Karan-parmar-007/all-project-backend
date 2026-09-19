# app/utils/html_sanitize.py
from __future__ import annotations

import bleach

ALLOWED_TAGS = [
    "p",
    "br",
    "h2",
    "h3",
    "h4",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "a",
    "ul",
    "ol",
    "li",
    "blockquote",
    "img",
    "code",
    "pre",
    "hr",
    "span",
    "figure",
    "figcaption",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title"],
}


def sanitize_project_html(raw: str | None) -> str:
    """Allow blog-style markup; strip scripts and unknown tags."""
    text = (raw or "").strip()
    if not text:
        return "<p></p>"
    if "<" not in text:
        paragraphs = bleach.clean(text).split("\n")
        parts = [f"<p>{p}</p>" if p.strip() else "<p><br></p>" for p in paragraphs]
        return "".join(parts)
    cleaned = bleach.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=["http", "https", "mailto"],
        strip=True,
    ).strip()
    return cleaned or "<p></p>"
