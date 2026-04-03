import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, cooklogs, dish, households, recommendation


logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()

origins = settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dish.router)
app.include_router(cooklogs.router)
app.include_router(recommendation.router)
app.include_router(households.router)


@app.on_event("startup")
async def startup_event():
    logger.info(
        "Starting %s v%s in %s mode",
        settings.APP_NAME,
        settings.APP_VERSION,
        "debug" if settings.DEBUG else "production",
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
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
def read_root():
    logger.debug("Root endpoint accessed")
    return {"Hello": "World"}


@app.get("/health")
def health_check():
    logger.debug("Health check endpoint accessed")
    return {"status": "Healthy"}
