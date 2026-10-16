# main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from karan_sso.fastapi import CSRFMiddleware

from app.api.main_router import main_router
from app.auth.sso import configure_sso, sso_settings
from app.config import auth_settings, cors_settings
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


configure_sso()

_docs_enabled = not auth_settings.is_production
app = FastAPI(
    title="All Projects API",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)
register_exception_handlers(app)

# CSRF first, CORS last so CORS wraps CSRF and preflights never hit CSRF.
# No anonymous POST endpoints exist, so only health is exempt.
app.add_middleware(
    CSRFMiddleware,
    exempt_prefixes=("/health", "/api/allprojects/health"),
    settings=sso_settings,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)
app.include_router(main_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
