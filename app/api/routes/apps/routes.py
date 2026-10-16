# app/api/routes/apps/routes.py
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.db_dependencies import PGSessionDep
from app.auth.dependencies import SsoIdentity
from app.auth.project_gate import (
    AppBootstrapResponse,
    bootstrap_project_app,
    optional_live_identity,
)

router = APIRouter(prefix="/apps", tags=["apps"])

OptionalLiveIdentityDep = Annotated[SsoIdentity | None, Depends(optional_live_identity)]


@router.get("/{project_slug}/bootstrap", response_model=AppBootstrapResponse)
async def app_bootstrap(
    project_slug: str,
    session: PGSessionDep,
    identity: OptionalLiveIdentityDep,
) -> AppBootstrapResponse:
    return await bootstrap_project_app(
        session=session,
        identity=identity,
        project_slug=project_slug,
    )
