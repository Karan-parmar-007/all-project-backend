# app/core/slug.py
from __future__ import annotations

from uuid import UUID

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def unique_slug(
    session: AsyncSession,
    model: type,
    text: str,
    *,
    slug_field: str = "slug",
    exclude_id: UUID | None = None,
) -> str:
    """Generate a URL-safe slug, appending a numeric suffix on collision."""
    base = slugify(text, max_length=150)
    candidate = base
    counter = 1
    while True:
        stmt = select(model).where(getattr(model, slug_field) == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            return candidate
        counter += 1
        candidate = f"{base}-{counter}"
