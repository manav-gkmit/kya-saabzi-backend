from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.utils.auth import get_current_user
from app.models.users import User


def test_create_dish(client: TestClient, db_session: Session, test_user: User):
    """
    Test creating a new dish.
    """

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    response = client.post(
        "/dishes/",
        json={"name": "test dish", "note": "test note"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test dish"
    assert "id" in data

    # Clean up dependency override
    del app.dependency_overrides[get_current_user]


def test_create_dish_existing(client: TestClient, db_session: Session, test_user: User):
    """
    Test creating a dish that already exists.
    """
    from app.models.dishes import Dish

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    dish = Dish(name="existing dish")
    db_session.add(dish)
    db_session.commit()

    response = client.post(
        "/dishes/",
        json={"name": "existing dish", "note": "test note"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "existing dish"
    assert data["id"] == str(dish.id)

    del app.dependency_overrides[get_current_user]
