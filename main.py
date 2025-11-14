from fastapi import FastAPI
from app.routers import auth, add_dish, get_logs

app = FastAPI()

app.include_router(auth.router)
app.include_router(add_dish.router)
app.include_router(get_logs.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
