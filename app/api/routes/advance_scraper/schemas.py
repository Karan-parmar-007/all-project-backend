# app/api/routes/advance_scraper/schemas.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StartScrapeRequest(BaseModel):
    """User-controlled inputs only. Parallelism / per-ZIP caps are server defaults."""

    search_term: str = Field(min_length=1, max_length=200)
    countries: list[str] = Field(default_factory=list)
    states: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)


class QuotaResponse(BaseModel):
    limit: int
    used: int
    remaining: int
    day: str
    reserved: int = 0


class LocationListResponse(BaseModel):
    items: list[str]


class StreamEvent(BaseModel):
    """NDJSON event shapes for the scrape stream."""

    type: str
    data: dict[str, Any] = Field(default_factory=dict)
