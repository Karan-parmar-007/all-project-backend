# app/api/dependencies.py
from typing import Annotated

from fastapi import Depends, Request

from app.api.db_dependencies import GarageClientDep, GarageStorageDep, PGSessionDep
from app.api.routes.health.health_service import HealthService
from app.api.routes.project.project_service import ProjectService
from app.api.routes.skill.skill_service import SkillService
from app.utils.garage import GarageStorage


def _get_mongo_db(request: Request):
    """Return Mongo DB handle if available, else None."""
    mongo = getattr(request.app.state, "mongo_session", None)
    if mongo is None:
        return None
    return mongo.db


def get_health_service(
    session: PGSessionDep, garage: GarageClientDep, request: Request
) -> HealthService:
    return HealthService(
        pg_session=session,
        garage_client=garage,
        mongo_db=_get_mongo_db(request),
    )


def get_project_service(
    session: PGSessionDep, garage: GarageStorageDep
) -> ProjectService:
    return ProjectService(pg_session=session, garage=garage)


def get_skill_service(
    session: PGSessionDep, garage: GarageStorageDep
) -> SkillService:
    return SkillService(pg_session=session, garage=garage)


type HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
type ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
type SkillServiceDep = Annotated[SkillService, Depends(get_skill_service)]
