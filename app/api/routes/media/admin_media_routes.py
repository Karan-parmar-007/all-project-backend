# app/api/routes/media/admin_media_routes.py
from __future__ import annotations

import re
import unicodedata

import uuid6
from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.db_dependencies import GarageStorageDep
from app.auth.dependencies import require_admin
from app.config import media_settings
from app.core.errors import MediaError
from app.utils.media_urls import api_media_url

router = APIRouter(
    prefix="/admin/media",
    tags=["admin:media"],
    dependencies=[Depends(require_admin)],
)


def _safe_filename(name: str | None) -> str:
    if not name:
        return "upload"
    name = unicodedata.normalize("NFKD", name)
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:200] or "upload"


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_body_image(
    garage: GarageStorageDep,
    file: UploadFile = File(...),
) -> dict[str, str]:
    content = await file.read()
    if not content:
        raise MediaError("File is empty")
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in media_settings.allowed_image_types:
        raise MediaError(f"Content type '{content_type}' is not an allowed image type")
    if len(content) > media_settings.MEDIA_MAX_IMAGE_BYTES:
        raise MediaError(
            f"File exceeds maximum size of {media_settings.MEDIA_MAX_IMAGE_BYTES} bytes"
        )
    filename = _safe_filename(file.filename)
    key = f"apps/posts/{uuid6.uuid7()}/{filename}"
    await garage.upload(key, content, content_type)
    url = api_media_url(key)
    if not url:
        raise MediaError("Failed to build media URL")
    return {"key": key, "url": url}
