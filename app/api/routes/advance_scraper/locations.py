# app/api/routes/advance_scraper/locations.py
"""API-facing location helpers — delegates to the vendored scraper package."""

from __future__ import annotations

from app.utils.advance_scraper.locations import list_cities, list_countries, list_states

__all__ = ["list_cities", "list_countries", "list_states"]
