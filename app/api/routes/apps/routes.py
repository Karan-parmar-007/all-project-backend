# app/api/routes/apps/routes.py
from fastapi import APIRouter

from app.api.db_dependencies import PGSessionDep
from app.auth.dependencies import SessionIdentityDep
from app.auth.project_gate import AppBootstrapResponse, bootstrap_project_app

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("/{project_slug}/bootstrap", response_model=AppBootstrapResponse)
async def app_bootstrap(
    project_slug: str,
    session: PGSessionDep,
    identity: SessionIdentityDep,
) -> AppBootstrapResponse:
    return await bootstrap_project_app(
        session=session,
        identity=identity,
        project_slug=project_slug,
    )
