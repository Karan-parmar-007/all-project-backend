import logging
from typing import Optional

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import db_settings

logger = logging.getLogger(__name__)


class MongoSession:
    """Manages the MongoDB connection via PyMongo's native AsyncMongoClient."""

    def __init__(self) -> None:
        self._client: Optional[AsyncMongoClient] = None
        self._db: Optional[AsyncDatabase] = None

    @property
    def client(self) -> Optional[AsyncMongoClient]:
        return self._client

    @property
    def db(self) -> Optional[AsyncDatabase]:
        return self._db

    async def verify_connection(self) -> None:
        """Verify connectivity at startup with a fast timeout."""
        try:
            self._client = AsyncMongoClient(
                db_settings.MONGO_URI,
                serverSelectionTimeoutMS=2000,
            )
            self._db = self._client[db_settings.MONGO_DB_NAME]
            await self._client.admin.command("ping")
            logger.info("MongoDB connected: %s", db_settings.MONGO_DB_NAME)
        except Exception as exc:
            logger.warning("MongoDB unavailable (non-fatal): %s", exc)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            logger.info("MongoDB connection closed")
