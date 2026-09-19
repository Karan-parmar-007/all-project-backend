# app/core/errors.py
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class DomainError(Exception):
    def __init__(self, message: str = "Domain error") -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class MediaError(DomainError):
    pass


class StorageError(DomainError):
    pass


class QuotaExceededError(DomainError):
    pass


class AppOfflineError(DomainError):
    """Live app is linked but its status does not allow access."""

    def __init__(self, message: str = "App is offline", *, code: str = "app_offline") -> None:
        self.code = code
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": exc.message})

    @app.exception_handler(ValidationError)
    async def validation_handler(
        _request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.message})

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(
        _request: Request, exc: UnauthorizedError
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": exc.message})

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(
        _request: Request, exc: ForbiddenError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": exc.message})

    @app.exception_handler(MediaError)
    async def media_handler(_request: Request, exc: MediaError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message})

    @app.exception_handler(StorageError)
    async def storage_handler(_request: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": exc.message})

    @app.exception_handler(QuotaExceededError)
    async def quota_handler(
        _request: Request, exc: QuotaExceededError
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": exc.message})

    @app.exception_handler(AppOfflineError)
    async def app_offline_handler(
        _request: Request, exc: AppOfflineError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": exc.message, "code": exc.code},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
