# app/api/routes/advance_scraper/service.py
from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes.advance_scraper.constants import (
    DAILY_COMPANY_LIMIT,
    DEFAULT_MAX_DISCOVERY_WORKERS,
    DEFAULT_PER_ZIP_CAP,
)
from app.api.routes.advance_scraper.engine import (
    get_location_api,
    get_scraper_runner_class,
)
from app.api.routes.advance_scraper.model import ApScraperDailyUsage
from app.api.routes.advance_scraper.schemas import QuotaResponse, StartScrapeRequest
from app.config import db_settings
from app.core.errors import ConflictError, QuotaExceededError, ValidationError
from app.live_apps import register_runtime_shutdown


APP_KEY = "advance_scraper"

_quota_engine = create_async_engine(
    db_settings.POSTGRES_URL,
    echo=False,
    connect_args={"server_settings": {"timezone": "UTC"}},
)
_quota_sessionmaker = async_sessionmaker(
    bind=_quota_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _event(event_type: str, **data: Any) -> str:
    return json.dumps({"type": event_type, "data": data}, default=str) + "\n"


@dataclass
class _StreamJob:
    id: str
    user_id: str
    search_term: str
    countries: list[str]
    states: list[str]
    cities: list[str]
    limit: int
    reserved: int
    events: queue.Queue = field(default_factory=queue.Queue)
    stop_event: threading.Event = field(default_factory=threading.Event)
    running: bool = True
    companies_emitted: int = 0
    seen_keys: set[str] = field(default_factory=set)
    worker: threading.Thread | None = None
    finished: bool = False


class AdvanceScraperService:
    """Stream scrape results; persist only daily usage quotas."""

    def __init__(self, pg_session: AsyncSession) -> None:
        self.pg = pg_session

    async def get_quota(self, user_id: str) -> QuotaResponse:
        day = _today_utc()
        async with _quota_sessionmaker() as session:
            result = await session.execute(
                select(ApScraperDailyUsage).where(
                    ApScraperDailyUsage.user_id == user_id,
                    ApScraperDailyUsage.day == day,
                )
            )
            row = result.scalar_one_or_none()
        used = int(row.companies_used) if row else 0
        remaining = max(0, DAILY_COMPANY_LIMIT - used)
        return QuotaResponse(
            limit=DAILY_COMPANY_LIMIT,
            used=used,
            remaining=remaining,
            day=day.isoformat(),
            reserved=0,
        )

    @staticmethod
    def list_countries() -> list[str]:
        _cities, list_countries, _states = get_location_api()
        return list_countries()

    @staticmethod
    def list_states() -> list[str]:
        _cities, _countries, list_states = get_location_api()
        return list_states()

    @staticmethod
    def list_cities(states: list[str] | None = None) -> list[str]:
        list_cities, _countries, _states = get_location_api()
        return list_cities(states if states else None)

    async def reserve_quota(self, user_id: str) -> int:
        """Atomically reserve remaining daily capacity. Returns reserved count."""
        day = _today_utc()
        async with _quota_sessionmaker() as session:
            async with session.begin():
                result = await session.execute(
                    select(ApScraperDailyUsage)
                    .where(
                        ApScraperDailyUsage.user_id == user_id,
                        ApScraperDailyUsage.day == day,
                    )
                    .with_for_update()
                )
                row = result.scalar_one_or_none()
                used = int(row.companies_used) if row else 0
                remaining = max(0, DAILY_COMPANY_LIMIT - used)
                if remaining <= 0:
                    raise QuotaExceededError(
                        f"Daily limit of {DAILY_COMPANY_LIMIT} companies reached. "
                        "Try again tomorrow."
                    )
                if row is None:
                    session.add(
                        ApScraperDailyUsage(
                            user_id=user_id,
                            day=day,
                            companies_used=remaining,
                        )
                    )
                else:
                    row.companies_used = used + remaining
                return remaining

    async def reconcile_quota(self, user_id: str, reserved: int, actual: int) -> None:
        """Release unused reserved quota after a run finishes."""
        if reserved <= 0:
            return
        actual = max(0, min(actual, reserved))
        refund = reserved - actual
        if refund <= 0:
            return
        day = _today_utc()
        async with _quota_sessionmaker() as session:
            async with session.begin():
                result = await session.execute(
                    select(ApScraperDailyUsage)
                    .where(
                        ApScraperDailyUsage.user_id == user_id,
                        ApScraperDailyUsage.day == day,
                    )
                    .with_for_update()
                )
                row = result.scalar_one_or_none()
                if row is None:
                    return
                row.companies_used = max(0, int(row.companies_used) - refund)

    async def start_stream(
        self, user_id: str, body: StartScrapeRequest
    ) -> AsyncIterator[str]:
        term = body.search_term.strip()
        if not term:
            raise ValidationError("search_term is required")

        reserved = await self.reserve_quota(user_id)
        job = run_registry.start(
            user_id=user_id,
            search_term=term,
            countries=body.countries,
            states=body.states,
            cities=body.cities,
            limit=reserved,
            reserved=reserved,
        )

        async def _generate() -> AsyncIterator[str]:
            try:
                yield _event(
                    "started",
                    runId=job.id,
                    limit=job.limit,
                    workers=DEFAULT_MAX_DISCOVERY_WORKERS,
                    perZipCap=DEFAULT_PER_ZIP_CAP,
                )
                while True:
                    try:
                        item = await asyncio.to_thread(job.events.get, True, 0.5)
                    except queue.Empty:
                        if job.finished:
                            break
                        continue
                    if item is None:
                        break
                    event_type, payload = item
                    yield _event(event_type, **payload)
            finally:
                job.stop_event.set()
                await self.reconcile_quota(user_id, reserved, job.companies_emitted)
                run_registry.forget(user_id, job.id)

        return _generate()


class _RunRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, _StreamJob] = {}

    def get(self, user_id: str) -> _StreamJob | None:
        with self._lock:
            return self._jobs.get(user_id)

    def forget(self, user_id: str, job_id: str) -> None:
        with self._lock:
            current = self._jobs.get(user_id)
            if current is not None and current.id == job_id:
                self._jobs.pop(user_id, None)

    def stop_all(self) -> None:
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            job.stop_event.set()
            job.events.put(
                (
                    "error",
                    {"message": "App was taken offline by an administrator."},
                )
            )
            job.events.put(None)

    def start(
        self,
        *,
        user_id: str,
        search_term: str,
        countries: list[str],
        states: list[str],
        cities: list[str],
        limit: int,
        reserved: int,
    ) -> _StreamJob:
        with self._lock:
            existing = self._jobs.get(user_id)
            if existing and existing.running and not existing.finished:
                raise ConflictError("A scrape is already running for this account")

            job = _StreamJob(
                id=str(uuid.uuid4()),
                user_id=user_id,
                search_term=search_term,
                countries=list(countries or []),
                states=list(states or []),
                cities=list(cities or []),
                limit=max(1, int(limit)),
                reserved=reserved,
            )
            self._jobs[user_id] = job

        worker = threading.Thread(
            target=self._worker,
            args=(job,),
            name=f"ap-scrape-{user_id[:8]}",
            daemon=True,
        )
        job.worker = worker
        worker.start()
        return job

    def _worker(self, job: _StreamJob) -> None:
        try:
            scraper_runner_cls = get_scraper_runner_class()

            def on_progress(info: dict) -> None:
                if job.stop_event.is_set():
                    return
                preview = info.get("companies_preview") or []
                for company in preview:
                    row = (
                        company.to_dict()
                        if hasattr(company, "to_dict")
                        else dict(company)
                    )
                    key = str(
                        row.get("place_id")
                        or row.get("cid")
                        or f"{row.get('name')}|{row.get('phone')}"
                    )
                    if key in job.seen_keys:
                        continue
                    job.seen_keys.add(key)
                    if job.companies_emitted >= job.limit:
                        job.stop_event.set()
                        break
                    job.companies_emitted += 1
                    job.events.put(("company", {"company": row}))

                status = str(info.get("status") or "")
                found = int(info.get("companies_found") or job.companies_emitted)
                job.events.put(
                    (
                        "progress",
                        {
                            "status": status,
                            "companiesFound": found,
                            "emitted": job.companies_emitted,
                            "limit": job.limit,
                        },
                    )
                )

            runner = scraper_runner_cls(
                search_term=job.search_term,
                countries=job.countries,
                states=job.states,
                cities=job.cities,
                limit=job.limit,
                per_zip_cap=DEFAULT_PER_ZIP_CAP,
                max_discovery_workers=DEFAULT_MAX_DISCOVERY_WORKERS,
                on_progress=on_progress,
                should_stop=job.stop_event.is_set,
            )
            companies = runner.run()
            for company in companies:
                row = (
                    company.to_dict() if hasattr(company, "to_dict") else dict(company)
                )
                key = str(
                    row.get("place_id")
                    or row.get("cid")
                    or f"{row.get('name')}|{row.get('phone')}"
                )
                if key in job.seen_keys:
                    continue
                if job.companies_emitted >= job.limit:
                    break
                job.seen_keys.add(key)
                job.companies_emitted += 1
                job.events.put(("company", {"company": row}))

            total = job.companies_emitted
            if job.stop_event.is_set():
                message = f"Stopped with {total:,} companies."
                status = "stopped"
            elif total:
                message = f"Collected {total:,} companies."
                status = "completed"
            else:
                message = "No companies were collected."
                status = "completed"
            job.events.put(
                (
                    "completed",
                    {
                        "status": status,
                        "message": message,
                        "companiesTotal": total,
                        "finishedAt": _utc_now(),
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            job.events.put(("error", {"message": str(exc)}))
        finally:
            job.running = False
            job.finished = True
            job.events.put(None)


run_registry = _RunRegistry()
register_runtime_shutdown(APP_KEY, run_registry.stop_all)
