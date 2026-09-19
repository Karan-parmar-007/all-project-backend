# app/api/routes/health/health_service.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.garage import check_connectivity


class HealthService:
    def __init__(
        self,
        pg_session: AsyncSession,
        garage_client: object,
        mongo_db: object | None = None,
    ) -> None:
        self.pg_session = pg_session
        self.garage_client = garage_client
        self.mongo_db = mongo_db

    async def check(self) -> dict[str, str]:
        result: dict[str, str] = {"status": "ok", "postgres": "ok", "garage": "ok", "mongo": "ok"}

        try:
            await self.pg_session.execute(text("SELECT 1"))
        except Exception as exc:
            result["status"] = "degraded"
            result["postgres"] = f"error: {exc}"

        try:
            await check_connectivity(self.garage_client)
        except Exception as exc:
            result["status"] = "degraded"
            result["garage"] = f"error: {exc}"

        try:
            if self.mongo_db is not None:
                await self.mongo_db.client.admin.command("ping")
            else:
                result["mongo"] = "not connected"
        except Exception as exc:
            result["status"] = "degraded"
            result["mongo"] = f"error: {exc}"

        return result
