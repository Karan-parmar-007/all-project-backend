# app/utils/garage.py
"""Universal S3-compatible Garage object storage utility.

Four Core Functions (the 4 Pillars):
1. upload_document - takes document/file and uploads it
2. delete_document - takes document key and deletes it
3. get_document - takes document key and retrieves content + metadata info
4. replace_document - takes new document and replaces old:
   uploads new first; if delete of old fails, rolls back (deletes) new upload and raises error.

Also provides the GarageStorage class for dependency injection and object-oriented usage.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, AsyncGenerator, Optional

import aioboto3
from botocore.client import BaseClient, Config
from botocore.exceptions import ClientError

from app.config import db_settings
from app.core.errors import NotFoundError, StorageError

logger = logging.getLogger(__name__)

_GARAGE_SERVICE = "s3"


@dataclass(frozen=True)
class DocumentInfo:
    """Detailed metadata and content returned by storage get operation."""
    key: str
    content: bytes
    content_type: str
    size_bytes: int
    metadata: dict[str, str]
    etag: str | None = None
    last_modified: datetime | None = None
    bucket: str = ""
    url: str = ""


@asynccontextmanager
async def get_isolated_garage_client() -> AsyncGenerator[BaseClient, None]:
    """Helper context manager to yield a standalone Garage client when not provided."""
    session = aioboto3.Session()
    garage_config = Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
    )
    async with session.client(
        _GARAGE_SERVICE,
        endpoint_url=db_settings.GARAGE_ENDPOINT_URL,
        aws_access_key_id=db_settings.GARAGE_ACCESS_KEY,
        aws_secret_access_key=db_settings.GARAGE_SECRET_KEY,
        region_name=db_settings.GARAGE_REGION_NAME,
        config=garage_config,
    ) as client:
        yield client


# ============================================================================
# Universal Storage Functions (Functional Interface)
# ============================================================================


async def upload_document(
    key: str,
    content: bytes,
    content_type: str,
    *,
    metadata: dict[str, str] | None = None,
    bucket: str | None = None,
    client: BaseClient | None = None,
) -> str:
    """1. Takes document and uploads it to Garage object storage.

    Returns the uploaded document key.
    """
    if client is None:
        async with get_isolated_garage_client() as isolated_client:
            return await upload_document(
                key=key,
                content=content,
                content_type=content_type,
                metadata=metadata,
                bucket=bucket,
                client=isolated_client,
            )

    target_bucket = bucket or db_settings.GARAGE_BUCKET_NAME
    params: dict[str, Any] = {
        "Bucket": target_bucket,
        "Key": key,
        "Body": content,
        "ContentType": content_type,
    }
    if metadata:
        params["Metadata"] = metadata

    try:
        await client.put_object(**params)
        logger.info("Uploaded document %s to bucket %s (%d bytes)", key, target_bucket, len(content))
        return key
    except ClientError as exc:
        logger.error("Failed to upload document %s to bucket %s: %s", key, target_bucket, exc)
        raise StorageError(f"Failed to upload document '{key}': {exc}") from exc


async def delete_document(
    key: str,
    *,
    bucket: str | None = None,
    ignore_missing: bool = True,
    client: BaseClient | None = None,
) -> None:
    """2. Takes document key and deletes it from Garage object storage."""
    if client is None:
        async with get_isolated_garage_client() as isolated_client:
            return await delete_document(
                key=key,
                bucket=bucket,
                ignore_missing=ignore_missing,
                client=isolated_client,
            )

    target_bucket = bucket or db_settings.GARAGE_BUCKET_NAME
    try:
        if not ignore_missing:
            exists = await check_document_exists(key, bucket=target_bucket, client=client)
            if not exists:
                raise NotFoundError(f"Document '{key}' does not exist in bucket '{target_bucket}'")

        await client.delete_object(Bucket=target_bucket, Key=key)
        logger.info("Deleted document %s from bucket %s", key, target_bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if ignore_missing and code in ("404", "NoSuchKey"):
            logger.debug("Document %s not found during delete, ignored", key)
            return
        logger.error("Failed to delete document %s from bucket %s: %s", key, target_bucket, exc)
        raise StorageError(f"Failed to delete document '{key}': {exc}") from exc


async def get_document(
    key: str,
    *,
    bucket: str | None = None,
    client: BaseClient | None = None,
) -> DocumentInfo:
    """3. Takes document key and retrieves its content, MIME type, and metadata info."""
    if client is None:
        async with get_isolated_garage_client() as isolated_client:
            return await get_document(
                key=key,
                bucket=bucket,
                client=isolated_client,
            )

    target_bucket = bucket or db_settings.GARAGE_BUCKET_NAME
    try:
        response = await client.get_object(Bucket=target_bucket, Key=key)
        content = await response["Body"].read()
        content_type = response.get("ContentType", "application/octet-stream")
        content_length = response.get("ContentLength", len(content))
        metadata = response.get("Metadata", {})
        etag = response.get("ETag")
        last_modified = response.get("LastModified")
        public_url = get_document_url(key, bucket=target_bucket)

        return DocumentInfo(
            key=key,
            content=content,
            content_type=content_type,
            size_bytes=content_length,
            metadata=metadata,
            etag=etag,
            last_modified=last_modified,
            bucket=target_bucket,
            url=public_url,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey"):
            raise NotFoundError(f"Document '{key}' not found in bucket '{target_bucket}'") from exc
        logger.error("Failed to get document %s from bucket %s: %s", key, target_bucket, exc)
        raise StorageError(f"Failed to get document '{key}': {exc}") from exc


async def replace_document(
    old_key: str | None,
    new_key: str,
    content: bytes,
    content_type: str,
    *,
    metadata: dict[str, str] | None = None,
    bucket: str | None = None,
    client: BaseClient | None = None,
) -> str:
    """4. Replaces an existing document with a new document.

    Process:
    - First uploads the new document to `new_key`.
    - If upload succeeds and `old_key` is provided (and different from `new_key`):
      attempts to delete the old document.
    - If deletion of the old document fails:
      automatically rolls back by deleting the newly uploaded document, and raises StorageError!

    Returns:
        The new_key upon complete success.
    """
    if client is None:
        async with get_isolated_garage_client() as isolated_client:
            return await replace_document(
                old_key=old_key,
                new_key=new_key,
                content=content,
                content_type=content_type,
                metadata=metadata,
                bucket=bucket,
                client=isolated_client,
            )

    target_bucket = bucket or db_settings.GARAGE_BUCKET_NAME

    # Step 1: Upload new document
    await upload_document(
        key=new_key,
        content=content,
        content_type=content_type,
        metadata=metadata,
        bucket=target_bucket,
        client=client,
    )

    # Step 2: Delete old document if present
    if old_key and old_key != new_key:
        try:
            await delete_document(
                key=old_key,
                bucket=target_bucket,
                ignore_missing=False,
                client=client,
            )
        except Exception as del_err:
            logger.warning(
                "Deleting old document '%s' failed after uploading new '%s'. Rolling back new upload: %s",
                old_key, new_key, del_err
            )
            # Rollback: delete the newly uploaded file
            try:
                await delete_document(
                    key=new_key,
                    bucket=target_bucket,
                    ignore_missing=True,
                    client=client,
                )
                logger.info("Rollback successful: deleted newly uploaded document '%s'", new_key)
            except Exception as rollback_err:
                logger.critical(
                    "CRITICAL: Rollback failed! Could not delete '%s': %s",
                    new_key, rollback_err
                )
            raise StorageError(
                f"Replace operation failed: could not delete old document '{old_key}'. "
                f"Newly uploaded document '{new_key}' was rolled back. Error: {del_err}"
            ) from del_err

    return new_key


async def check_document_exists(
    key: str,
    *,
    bucket: str | None = None,
    client: BaseClient | None = None,
) -> bool:
    """Check if a document exists in the bucket."""
    if client is None:
        async with get_isolated_garage_client() as isolated_client:
            return await check_document_exists(key=key, bucket=bucket, client=isolated_client)

    target_bucket = bucket or db_settings.GARAGE_BUCKET_NAME
    try:
        await client.head_object(Bucket=target_bucket, Key=key)
        return True
    except ClientError:
        return False


def get_document_url(
    key: str,
    *,
    bucket: str | None = None,
) -> str:
    """Return the direct endpoint URL for the document."""
    target_bucket = bucket or db_settings.GARAGE_BUCKET_NAME
    endpoint = db_settings.GARAGE_ENDPOINT_URL.rstrip("/")
    clean_key = key.lstrip("/")
    return f"{endpoint}/{target_bucket}/{clean_key}"


async def get_presigned_document_url(
    key: str,
    *,
    expires_in: int = 3600,
    bucket: str | None = None,
    client: BaseClient | None = None,
) -> str:
    """Generate a presigned GET URL for the document."""
    if client is None:
        async with get_isolated_garage_client() as isolated_client:
            return await get_presigned_document_url(
                key=key,
                expires_in=expires_in,
                bucket=bucket,
                client=isolated_client,
            )

    target_bucket = bucket or db_settings.GARAGE_BUCKET_NAME
    url = await client.generate_presigned_url(
        "get_object",
        Params={"Bucket": target_bucket, "Key": key},
        ExpiresIn=expires_in,
    )
    return url


# ============================================================================
# Object-Oriented Interface (GarageStorage)
# ============================================================================


class GarageStorage:
    """OOP abstraction wrapping a client, delegating to the universal functions."""

    def __init__(self, client: BaseClient, default_bucket: str | None = None) -> None:
        self._client = client
        self._default_bucket = default_bucket or db_settings.GARAGE_BUCKET_NAME

    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: str,
        *,
        metadata: dict[str, str] | None = None,
        bucket: str | None = None,
    ) -> str:
        return await upload_document(
            key=key,
            content=content,
            content_type=content_type,
            metadata=metadata,
            bucket=bucket or self._default_bucket,
            client=self._client,
        )

    async def delete(
        self,
        key: str,
        *,
        bucket: str | None = None,
        ignore_missing: bool = True,
    ) -> None:
        return await delete_document(
            key=key,
            bucket=bucket or self._default_bucket,
            ignore_missing=ignore_missing,
            client=self._client,
        )

    async def get(
        self,
        key: str,
        *,
        bucket: str | None = None,
    ) -> DocumentInfo:
        return await get_document(
            key=key,
            bucket=bucket or self._default_bucket,
            client=self._client,
        )

    async def download(
        self,
        key: str,
        *,
        bucket: str | None = None,
    ) -> tuple[bytes, str]:
        doc = await self.get(key, bucket=bucket)
        return doc.content, doc.content_type

    async def replace(
        self,
        old_key: str | None,
        new_key: str,
        content: bytes,
        content_type: str,
        *,
        metadata: dict[str, str] | None = None,
        bucket: str | None = None,
    ) -> str:
        return await replace_document(
            old_key=old_key,
            new_key=new_key,
            content=content,
            content_type=content_type,
            metadata=metadata,
            bucket=bucket or self._default_bucket,
            client=self._client,
        )

    async def exists(self, key: str, *, bucket: str | None = None) -> bool:
        return await check_document_exists(
            key=key,
            bucket=bucket or self._default_bucket,
            client=self._client,
        )

    async def get_presigned_url(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        bucket: str | None = None,
    ) -> str:
        return await get_presigned_document_url(
            key=key,
            expires_in=expires_in,
            bucket=bucket or self._default_bucket,
            client=self._client,
        )

    def get_url(self, key: str, *, bucket: str | None = None) -> str:
        return get_document_url(key, bucket=bucket or self._default_bucket)
