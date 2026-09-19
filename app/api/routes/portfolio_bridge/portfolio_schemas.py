# app/api/routes/portfolio_bridge/portfolio_schemas.py
from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.api.schemas.common import CamelModel


class PortfolioProjectCard(CamelModel):
    """Slim project card for portfolio display."""

    id: UUID
    name: str
    slug: str
    short_description: str
    status: str
    live_url: str | None = None
    github_url: str | None = None
    cover_image_key: str | None = None
    cover_image_url: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)


class PortfolioFeaturedResponse(CamelModel):
    items: list[PortfolioProjectCard]


class PortfolioProjectsResponse(CamelModel):
    items: list[PortfolioProjectCard]
