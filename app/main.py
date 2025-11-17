from fastapi import FastAPI
from app.routers import auth, dish, cooklogs


app = FastAPI()


app.include_router(auth.router)
app.include_router(dish.router)
app.include_router(cooklogs.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
