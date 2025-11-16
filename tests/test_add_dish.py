import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import uuid
from app.main import app
from app.database.db import get_db
from app.deps import get_current_user
from app.models.users import User
from app.models.dishes import Dish
from app.models.cooklogs import CookLog


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


mock_user = User(
    id=uuid.uuid4(),
    email="test@example.com",
    username="testuser",
    hashed_password="password",
)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


def override_get_current_user():
    return mock_user


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    Dish.metadata.create_all(bind=engine)
    CookLog.metadata.create_all(bind=engine)
    User.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        User.metadata.drop_all(bind=engine)
        CookLog.metadata.drop_all(bind=engine)
        Dish.metadata.drop_all(bind=engine)


def test_create_dish(db_session):
    dish_data = {"name": "Test Dish"}

    response = client.post("/routers/add_dish", json=dish_data)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == dish_data["name"]
    assert "id" in data

    dish = db_session.query(Dish).filter(Dish.name == "Test Dish").first()
    assert dish is not None
    assert dish.name == "Test Dish"

    cooklog = db_session.query(CookLog).filter(CookLog.dish_id == dish.id).first()
    assert cooklog is not None
    assert cooklog.user_id == mock_user.id
