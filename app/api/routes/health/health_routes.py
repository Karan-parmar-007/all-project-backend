# app/api/routes/health/health_routes.py
from fastapi import APIRouter

from app.api.dependencies import HealthServiceDep
from app.api.routes.health.health_schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check(service: HealthServiceDep) -> HealthResponse:
    result = await service.check()
    return HealthResponse(**result)
