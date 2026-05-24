from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.cooklogs import router as cooklogs_router
from app.api.v1.dish import router as dish_router
from app.api.v1.households import router as households_router
from app.api.v1.recommendation import router as recommendation_router

api_router = APIRouter(deprecated=True)
api_router.include_router(auth_router)
api_router.include_router(dish_router)
api_router.include_router(cooklogs_router)
api_router.include_router(recommendation_router)
api_router.include_router(households_router)
