# tests/test_project_service.py
from io import BytesIO
import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.project.project_service import ProjectService
from app.api.routes.project.model import ApProject
from app.utils.garage import GarageStorage
from tests.conftest import FakeGarageClient


def _mock_upload(filename: str = "banner.png", content: bytes = b"fake-image-bytes") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers={"content-type": "image/png"},
    )


@pytest.mark.asyncio
async def test_project_cover_image_lifecycle(
    app_client,
    fake_garage_client: FakeGarageClient,
) -> None:
    from main import app
    from app.db.postgres_session import PostgresSession

    pg_session_gen = app.state.postgres_session.get_session()
    session: AsyncSession = await anext(pg_session_gen)

    garage = GarageStorage(fake_garage_client, default_bucket="test-bucket")
    service = ProjectService(pg_session=session, garage=garage)

    statuses = await service.list_statuses()
    offline = next(s for s in statuses if s.slug == "offline")

    # 1. Create project with cover image
    cover = _mock_upload("sample_cover.png", b"image-v1-bytes")
    created = await service.create_project(
        name="Test Service Project",
        short_description="Short desc",
        long_description="Long desc",
        status_id=offline.id,
        cover_image=cover,
    )
    assert created.name == "Test Service Project"
    assert created.cover_image_key is not None
    assert "apps/covers" in created.cover_image_key
    assert await garage.exists(created.cover_image_key) is True

    # 2. Update project with new cover image (should trigger replace with rollback safety)
    old_key = created.cover_image_key
    new_cover = _mock_upload("sample_cover_v2.png", b"image-v2-bytes")
    updated = await service.update_project(
        project_id=created.id,
        fields={},
        tag_ids=None,
        cover_image=new_cover,
    )
    assert updated.cover_image_key != old_key
    assert await garage.exists(updated.cover_image_key) is True
    assert await garage.exists(old_key) is False

    # 3. Delete cover
    await service.delete_cover(created.id)
    refreshed = await service.admin_get(created.id)
    assert refreshed.cover_image_key is None
    assert await garage.exists(updated.cover_image_key) is False

    # 4. Clean up test project
    await service.delete_project(created.id)
