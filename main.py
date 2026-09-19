# main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.main_router import main_router
from app.api.middleware.csrf import CSRFMiddleware
from app.api.routes.auth import auth_routes
from app.config import cors_settings
from app.core.errors import register_exception_handlers
from app.db.garage import GarageSession
from app.db.mongo_session import MongoSession
from app.db.postgres_session import PostgresSession
from bootstrap import run_bootstrap

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    postgres_session = PostgresSession()
    garage_session = GarageSession()
    mongo_session = MongoSession()

    # Set state immediately so dependencies are always present
    app.state.postgres_session = postgres_session
    app.state.garage_session = garage_session
    app.state.mongo_session = mongo_session

    try:
        await postgres_session.verify_connection()
        logger.info("PostgreSQL connected successfully")
        await run_bootstrap(postgres_session._sessionmaker)
    except Exception as exc:
        logger.exception("PostgreSQL verify or bootstrap failed: %s", exc)

    try:
        await mongo_session.verify_connection()
    except Exception as exc:
        logger.warning("MongoDB verify failed: %s", exc)

    yield

    await postgres_session.dispose()
    await mongo_session.close()


app = FastAPI(title="All Projects API", lifespan=lifespan)
register_exception_handlers(app)

# CSRF first, CORS last so CORS wraps CSRF and preflights never hit CSRF.
app.add_middleware(CSRFMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(main_router)
# Local-dev cookie path: refresh_token is scoped to /api/auth
app.include_router(auth_routes.router, prefix="/api")
