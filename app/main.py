from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.v1.api import api_router
from app.api.v2.api import api_v2_router
from app.config import settings
from app.core.exceptions import (
    AppError,
    AuthError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.utils.api_migration import add_v1_migration_headers, migration_exposed_headers
from app.utils.logging_config import configure_logging
from app.utils.rate_limit import limiter

configure_logging(debug=settings.DEBUG)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle app lifecycle."""
    logger.info(
        "Starting %s v%s in %s mode",
        settings.APP_NAME,
        settings.APP_VERSION,
        "debug" if settings.DEBUG else "production",
    )
    yield


app = FastAPI(lifespan=lifespan)

# --- Rate limiting & Exception Handlers ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.error("Validation error for %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


_ERROR_STATUS_MAP = {
    AuthError: status.HTTP_401_UNAUTHORIZED,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    status_code = next(
        (code for exc_cls, code in _ERROR_STATUS_MAP.items() if isinstance(exc, exc_cls)),
        status.HTTP_400_BAD_REQUEST,
    )

    logger.warning("App error: %s", str(exc))
    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=migration_exposed_headers(),
)

# --- Routers ---
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_v2_router, prefix="/api/v2")


@app.middleware("http")
async def log_requests(request: Request, call_next: RequestResponseEndpoint) -> Response:
    logger.info("Incoming request: %s %s", request.method, request.url.path)
    response = None
    try:
        response = await call_next(request)
        add_v1_migration_headers(path=request.url.path, response=response)
        return response
    except Exception as exc:
        logger.exception(
            "Request failed: %s %s -> %s",
            request.method,
            request.url.path,
            exc,
        )
        raise
    finally:
        logger.info(
            "Completed request: %s %s -> %s",
            request.method,
            request.url.path,
            response.status_code if response is not None else "error",
        )


@app.get("/")
def read_root() -> dict[str, str]:
    logger.debug("Root endpoint accessed")
    return {"Hello": "World"}


@app.get("/health")
def health_check() -> dict[str, str]:
    logger.debug("Health check endpoint accessed")
    return {"status": "Healthy"}
