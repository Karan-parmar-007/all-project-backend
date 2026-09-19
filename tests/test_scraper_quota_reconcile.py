# tests/test_scraper_quota_reconcile.py
"""Quota reservation / reconciliation logic without a live Maps scrape."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.advance_scraper.constants import DAILY_COMPANY_LIMIT
from app.api.routes.advance_scraper.service import AdvanceScraperService
from app.core.errors import QuotaExceededError


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeSession:
    def __init__(self, row=None):
        self.row = row
        self.added = []
        self.begin_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def begin(self):
        outer = self

        class _Begin:
            async def __aenter__(self_inner):
                outer.begin_calls += 1
                return outer

            async def __aexit__(self_inner, *args):
                return False

        return _Begin()

    async def execute(self, _stmt):
        return _FakeResult(self.row)

    def add(self, obj):
        self.added.append(obj)
        self.row = obj


@pytest.mark.asyncio
async def test_reserve_quota_creates_row_at_full_remaining() -> None:
    fake = _FakeSession(row=None)
    service = AdvanceScraperService(pg_session=AsyncMock())
    with patch(
        "app.api.routes.advance_scraper.service._quota_sessionmaker",
        return_value=fake,
    ):
        reserved = await service.reserve_quota("u1")
    assert reserved == DAILY_COMPANY_LIMIT
    assert fake.added
    assert fake.added[0].companies_used == DAILY_COMPANY_LIMIT


@pytest.mark.asyncio
async def test_reserve_quota_exhausted_raises() -> None:
    row = SimpleNamespace(companies_used=DAILY_COMPANY_LIMIT)
    fake = _FakeSession(row=row)
    service = AdvanceScraperService(pg_session=AsyncMock())
    with patch(
        "app.api.routes.advance_scraper.service._quota_sessionmaker",
        return_value=fake,
    ):
        with pytest.raises(QuotaExceededError):
            await service.reserve_quota("u1")


@pytest.mark.asyncio
async def test_reconcile_refunds_unused_reservation() -> None:
    row = SimpleNamespace(companies_used=50)
    fake = _FakeSession(row=row)
    service = AdvanceScraperService(pg_session=AsyncMock())
    with patch(
        "app.api.routes.advance_scraper.service._quota_sessionmaker",
        return_value=fake,
    ):
        await service.reconcile_quota("u1", reserved=50, actual=12)
    assert row.companies_used == 12


@pytest.mark.asyncio
async def test_reconcile_no_op_when_fully_used() -> None:
    row = SimpleNamespace(companies_used=50)
    fake = _FakeSession(row=row)
    service = AdvanceScraperService(pg_session=AsyncMock())
    with patch(
        "app.api.routes.advance_scraper.service._quota_sessionmaker",
        return_value=fake,
    ):
        await service.reconcile_quota("u1", reserved=50, actual=50)
    assert row.companies_used == 50
