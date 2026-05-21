"""API router aggregator for V2 endpoints."""

from fastapi import APIRouter

from app.api.v2.auth import router as auth_router
from app.api.v2.cooklogs import router as cooklogs_router
from app.api.v2.dish import router as dish_router
from app.api.v2.households import router as households_router
from app.api.v2.recommendation import router as recommendation_router

api_v2_router = APIRouter()
api_v2_router.include_router(auth_router)
api_v2_router.include_router(dish_router)
api_v2_router.include_router(cooklogs_router)
api_v2_router.include_router(recommendation_router)
api_v2_router.include_router(households_router)
