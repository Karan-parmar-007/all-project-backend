# app/api/db_dependencies.py
from collections.abc import AsyncGenerator
from typing import Annotated

from botocore.client import BaseClient
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.garage import GarageStorage


async def _get_pg_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    postgres_manager = request.app.state.postgres_session
    async for session in postgres_manager.get_session():
        yield session


async def _get_garage_client(request: Request) -> AsyncGenerator[BaseClient, None]:
    garage_manager = request.app.state.garage_session
    async for client in garage_manager.get_client():
        yield client


async def _get_garage_storage(
    client: "GarageClientDep",
) -> GarageStorage:
    return GarageStorage(client)


type PGSessionDep = Annotated[AsyncSession, Depends(_get_pg_session)]
type GarageClientDep = Annotated[BaseClient, Depends(_get_garage_client)]
type GarageStorageDep = Annotated[GarageStorage, Depends(_get_garage_storage)]
