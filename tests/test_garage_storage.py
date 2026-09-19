# tests/test_garage_storage.py
import pytest
from app.utils.garage import (
    GarageStorage,
    DocumentInfo,
    upload_document,
    delete_document,
    get_document,
    replace_document,
    check_document_exists,
    get_document_url,
)
from app.core.errors import NotFoundError, StorageError
from tests.conftest import FakeGarageClient


@pytest.mark.asyncio
async def test_functional_interface(fake_garage_client: FakeGarageClient) -> None:
    """Test the core functional interface in utils/garage.py."""
    bucket = "test-bucket"

    # 1. upload_document
    key = await upload_document(
        "docs/contract.pdf",
        b"%PDF contract content",
        "application/pdf",
        metadata={"author": "karan"},
        bucket=bucket,
        client=fake_garage_client,
    )
    assert key == "docs/contract.pdf"
    assert await check_document_exists(key, bucket=bucket, client=fake_garage_client) is True

    # 2. get_document
    doc = await get_document(key, bucket=bucket, client=fake_garage_client)
    assert isinstance(doc, DocumentInfo)
    assert doc.key == key
    assert doc.content == b"%PDF contract content"
    assert doc.content_type == "application/pdf"
    assert doc.metadata == {"author": "karan"}

    # 3. replace_document (success)
    new_key = await replace_document(
        old_key=key,
        new_key="docs/contract_v2.pdf",
        content=b"%PDF contract content v2",
        content_type="application/pdf",
        bucket=bucket,
        client=fake_garage_client,
    )
    assert new_key == "docs/contract_v2.pdf"
    assert await check_document_exists("docs/contract_v2.pdf", bucket=bucket, client=fake_garage_client) is True
    assert await check_document_exists(key, bucket=bucket, client=fake_garage_client) is False

    # 4. delete_document
    await delete_document(new_key, bucket=bucket, client=fake_garage_client)
    assert await check_document_exists(new_key, bucket=bucket, client=fake_garage_client) is False


@pytest.mark.asyncio
async def test_replace_failure_triggers_rollback(fake_garage_client: FakeGarageClient) -> None:
    """Test replace rollback when deleting the old document fails."""
    bucket = "test-bucket"
    old_key = await upload_document(
        "docs/old_precious.txt",
        b"precious old version",
        "text/plain",
        bucket=bucket,
        client=fake_garage_client,
    )
    assert await check_document_exists(old_key, bucket=bucket, client=fake_garage_client) is True

    # Simulate delete failure on old document
    fake_garage_client.fail_delete_for.add(old_key)

    # Attempt replace -> must fail and rollback (delete) new upload
    with pytest.raises(StorageError, match="could not delete old document"):
        await replace_document(
            old_key=old_key,
            new_key="docs/new_attempt.txt",
            content=b"new version",
            content_type="text/plain",
            bucket=bucket,
            client=fake_garage_client,
        )

    # Old document must still exist
    assert await check_document_exists(old_key, bucket=bucket, client=fake_garage_client) is True
    # Newly uploaded document must have been rolled back (deleted)
    assert await check_document_exists("docs/new_attempt.txt", bucket=bucket, client=fake_garage_client) is False


@pytest.mark.asyncio
async def test_oop_garage_storage_wrapper(fake_garage_client: FakeGarageClient) -> None:
    """Test GarageStorage OOP class interface."""
    storage = GarageStorage(fake_garage_client, default_bucket="test-bucket")

    # Upload
    key = await storage.upload("files/test.txt", b"hello world", "text/plain")
    assert key == "files/test.txt"

    # Get & Download
    doc = await storage.get("files/test.txt")
    assert doc.content == b"hello world"
    content, ct = await storage.download("files/test.txt")
    assert content == b"hello world"
    assert ct == "text/plain"

    # Replace
    replaced = await storage.replace(
        old_key="files/test.txt",
        new_key="files/test_v2.txt",
        content=b"hello world v2",
        content_type="text/plain",
    )
    assert replaced == "files/test_v2.txt"
    assert await storage.exists("files/test.txt") is False
    assert await storage.exists("files/test_v2.txt") is True

    # Delete
    await storage.delete("files/test_v2.txt")
    assert await storage.exists("files/test_v2.txt") is False
