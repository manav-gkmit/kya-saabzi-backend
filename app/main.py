import logging
import structlog
from collections.abc import AsyncGenerator
from typing import Callable

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.api import api_router
from app.config import settings
from app.utils.rate_limit import limiter

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(message)s",
)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.DEBUG if settings.DEBUG else logging.INFO
    ),
    logger_factory=structlog.PrintLoggerFactory(),
)
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

# --- Rate limiting ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(api_router, prefix="/api/v1")


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    logger.info("Incoming request: %s %s", request.method, request.url.path)
    response = None
    try:
        response = await call_next(request)
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
