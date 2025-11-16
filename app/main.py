from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, add_dish, get_logs, recommendation


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(add_dish.router)
app.include_router(get_logs.router)
app.include_router(recommendation.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
