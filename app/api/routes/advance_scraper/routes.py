# app/api/routes/advance_scraper/routes.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.db_dependencies import PGSessionDep
from app.api.routes.advance_scraper.schemas import (
    LocationListResponse,
    QuotaResponse,
    StartScrapeRequest,
)
from app.api.routes.advance_scraper.service import APP_KEY, AdvanceScraperService
from app.auth.project_gate import ProjectAppAccess, require_project_app

router = APIRouter(
    prefix="/apps/{project_slug}/advance-scraper",
    tags=["advance-scraper"],
)

ProjectAppDep = Annotated[
    ProjectAppAccess, Depends(require_project_app(APP_KEY))
]


def get_scraper_service(session: PGSessionDep) -> AdvanceScraperService:
    return AdvanceScraperService(pg_session=session)


ScraperServiceDep = Annotated[AdvanceScraperService, Depends(get_scraper_service)]


@router.get("/quota", response_model=QuotaResponse)
async def get_quota(
    access: ProjectAppDep,
    service: ScraperServiceDep,
) -> QuotaResponse:
    return await service.get_quota(access.identity.user_id)


@router.get("/locations/countries", response_model=LocationListResponse)
async def countries(
    _: ProjectAppDep,
    service: ScraperServiceDep,
) -> LocationListResponse:
    return LocationListResponse(items=service.list_countries())


@router.get("/locations/states", response_model=LocationListResponse)
async def states(
    _: ProjectAppDep,
    service: ScraperServiceDep,
) -> LocationListResponse:
    return LocationListResponse(items=service.list_states())


@router.get("/locations/cities", response_model=LocationListResponse)
async def cities(
    _: ProjectAppDep,
    service: ScraperServiceDep,
    state: list[str] | None = Query(default=None),
) -> LocationListResponse:
    return LocationListResponse(items=service.list_cities(state))


@router.post("/runs/stream")
async def stream_run(
    body: StartScrapeRequest,
    access: ProjectAppDep,
    service: ScraperServiceDep,
) -> StreamingResponse:
    generator = await service.start_stream(access.identity.user_id, body)
    return StreamingResponse(
        generator,
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
