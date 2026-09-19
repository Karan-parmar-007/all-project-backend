# tests/conftest.py
from collections.abc import AsyncIterator
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest
from botocore.exceptions import ClientError
from app.db.postgres_session import PostgresSession


class FakeGarageClient:
    """In-memory fake for botocore S3 client used with Garage."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}
        self.fail_delete_for: set[str] = set()

    async def put_object(
        self,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
        Metadata: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.objects[(Bucket, Key)] = {
            "Body": Body,
            "ContentType": ContentType,
            "Metadata": Metadata or {},
        }
        return {"ETag": '"fake-etag"'}

    async def get_object(self, Bucket: str, Key: str, **kwargs: Any) -> dict[str, Any]:
        target = (Bucket, Key)
        if target not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
                "GetObject",
            )
        entry = self.objects[target]
        body_mock = AsyncMock()
        body_mock.read.return_value = entry["Body"]
        return {
            "Body": body_mock,
            "ContentType": entry["ContentType"],
            "ContentLength": len(entry["Body"]),
            "Metadata": entry["Metadata"],
            "ETag": '"fake-etag"',
        }

    async def delete_object(self, Bucket: str, Key: str, **kwargs: Any) -> dict[str, Any]:
        if Key in self.fail_delete_for:
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "Simulated delete failure"}},
                "DeleteObject",
            )
        target = (Bucket, Key)
        self.objects.pop(target, None)
        return {}

    async def head_object(self, Bucket: str, Key: str, **kwargs: Any) -> dict[str, Any]:
        target = (Bucket, Key)
        if target not in self.objects:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}},
                "HeadObject",
            )
        entry = self.objects[target]
        return {
            "ContentLength": len(entry["Body"]),
            "ContentType": entry["ContentType"],
        }

    async def head_bucket(self, Bucket: str, **kwargs: Any) -> dict[str, Any]:
        return {}


class FakeGarageSession:
    def __init__(self, client: FakeGarageClient) -> None:
        self.client = client

    async def get_client(self):
        yield self.client


@pytest.fixture
def fake_garage_client() -> FakeGarageClient:
    return FakeGarageClient()


@pytest.fixture
async def app_client(fake_garage_client: FakeGarageClient) -> AsyncIterator[httpx.AsyncClient]:
    from main import app
    
    pg_session = PostgresSession()
    app.state.postgres_session = pg_session
    app.state.garage_session = FakeGarageSession(fake_garage_client)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await pg_session.dispose()
