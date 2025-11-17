from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, cooklogs, dish, recommendation


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dish.router)
app.include_router(cooklogs.router)
app.include_router(recommendation.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
