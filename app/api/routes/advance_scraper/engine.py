# app/api/routes/advance_scraper/engine.py
"""Load the vendored Maps scraper engine from app.utils.advance_scraper."""

from __future__ import annotations

from typing import Any

from app.utils.advance_scraper.locations import (
    list_cities,
    list_countries,
    list_states,
)
from app.utils.advance_scraper.runner import ScraperRunner


def get_location_api() -> tuple[Any, Any, Any]:
    """Return (list_cities, list_countries, list_states)."""
    return list_cities, list_countries, list_states


def get_scraper_runner_class() -> Any:
    return ScraperRunner
