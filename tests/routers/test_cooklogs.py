from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.utils.auth import get_current_user
from app.models.users import User
from app.models.dishes import Dish
from app.models.cooklogs import CookLog


def test_get_cooklogs(client: TestClient, db_session: Session, test_user: User):
    """
    Test getting cooklogs for the current user.
    """

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    dish = Dish(name="test dish")
    db_session.add(dish)
    db_session.commit()
    db_session.refresh(dish)

    cooklog = CookLog(user_id=test_user.id, dish_id=dish.id, note="test note")
    db_session.add(cooklog)
    db_session.commit()
    db_session.refresh(cooklog)

    response = client.get("/cooklogs/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["note"] == "test note"
    assert data[0]["dish"]["name"] == "test dish"

    del app.dependency_overrides[get_current_user]


def test_delete_cooklog(client: TestClient, db_session: Session, test_user: User):
    """
    Test deleting a cooklog entry.
    """

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    dish = Dish(name="test dish")
    db_session.add(dish)
    db_session.commit()
    db_session.refresh(dish)

    cooklog = CookLog(user_id=test_user.id, dish_id=dish.id, note="test note")
    db_session.add(cooklog)
    db_session.commit()
    db_session.refresh(cooklog)

    cooklog_id = cooklog.id

    response = client.delete(f"/cooklogs/{cooklog_id}")
    assert response.status_code == 204

    deleted_cooklog = (
        db_session.query(CookLog).filter(CookLog.id == cooklog_id).first()
    )
    assert deleted_cooklog.deleted_at is not None

    del app.dependency_overrides[get_current_user]


# test to try and get logs of other user
# test to try and delete logs of other user


def test_delete_foreign_cooklog(
    client: TestClient, db_session: Session, test_user: User, other_user: User
):
    """
    Test that a user cannot delete a cooklog that does not belong to them.
    """

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    dish = Dish(name="test dish")
    db_session.add(dish)
    db_session.commit()
    db_session.refresh(dish)

    cooklog = CookLog(user_id=other_user.id, dish_id=dish.id, note="test note")
    db_session.add(cooklog)
    db_session.commit()
    db_session.refresh(cooklog)

    cooklog_id = cooklog.id

    response = client.delete(f"/cooklogs/{cooklog_id}")
    assert response.status_code == 403

    del app.dependency_overrides[get_current_user]


def test_get_foreign_logs(
    client: TestClient, db_session: Session, test_user: User, other_user: User
):
    """
    Test that a user cannot get the cooklogs of another user.
    """

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    dish = Dish(name="test dish")
    db_session.add(dish)
    db_session.commit()
    db_session.refresh(dish)

    cooklog = CookLog(user_id=other_user.id, dish_id=dish.id, note="test note")
    db_session.add(cooklog)
    db_session.commit()
    db_session.refresh(cooklog)

    response = client.get("/cooklogs/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0

    del app.dependency_overrides[get_current_user]
