# app/api/routes/advance_scraper/model.py
from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar

from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint
from sqlmodel import Field, SQLModel, func


class ApScraperDailyUsage(SQLModel, table=True):
    """Per-user daily company quota. Scraped companies are never persisted."""

    __tablename__: ClassVar[str] = "ap_scraper_daily_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_ap_scraper_daily_usage_user_day"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    day: date = Field(sa_column=Column(Date, nullable=False, index=True))
    companies_used: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )
