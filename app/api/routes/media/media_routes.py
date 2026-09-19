# app/api/routes/media/media_routes.py
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api.db_dependencies import GarageStorageDep
from app.config import media_settings
from app.core.errors import NotFoundError
from app.utils.media_urls import is_allowed_media_key

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{object_key:path}")
async def get_media(
    object_key: str,
    request: Request,
    garage: GarageStorageDep,
) -> Response:
    if not is_allowed_media_key(object_key):
        raise NotFoundError("Media not found")

    if_none_match = request.headers.get("if-none-match")
    try:
        doc = await garage.get(object_key)
    except NotFoundError:
        raise NotFoundError("Media not found") from None

    etag = f'"{doc.etag or doc.key}"'
    cache = (
        f"public, max-age={media_settings.MEDIA_CACHE_MAX_AGE_SECONDS}, immutable"
    )
    if if_none_match and if_none_match.strip() == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": cache})

    return Response(
        content=doc.content,
        media_type=doc.content_type or "application/octet-stream",
        headers={
            "ETag": etag,
            "Cache-Control": cache,
            "Content-Length": str(doc.size_bytes),
        },
    )
