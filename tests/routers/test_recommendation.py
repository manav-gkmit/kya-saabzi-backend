from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.utils.auth import get_current_user
from app.models.users import User
from app.models.dishes import Dish
from app.models.cooklogs import CookLog
from app.utils.security import get_password_hash


def test_get_recommendation(client: TestClient, db_session: Session, test_user: User):
    """
    Test getting dish recommendations.
    """

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    other_user_1 = User(username="other1", email="other1@example.com", hashed_password=get_password_hash("password"))
    other_user_2 = User(username="other2", email="other2@example.com", hashed_password=get_password_hash("password"))
    db_session.add_all([other_user_1, other_user_2])
    db_session.commit()

    dish1 = Dish(name="dishA")
    dish2 = Dish(name="dishB")
    dish3 = Dish(name="dishC")
    dish4 = Dish(name="dishD")
    dish5 = Dish(name="dishE")
    dish6 = Dish(name="dishF")
    dish7 = Dish(name="dishG")
    dish8 = Dish(name="dishH")
    dish9 = Dish(name="dishI")
    db_session.add_all([dish1, dish2, dish3, dish4, dish5, dish6, dish7, dish8, dish9])
    db_session.commit()

    for i in range(5):
        cooklog = CookLog(user_id=test_user.id, dish_id=locals()[f"dish{i+1}"].id)
        db_session.add(cooklog)
    db_session.commit()

    cooklog1 = CookLog(user_id=other_user_1.id, dish_id=dish6.id, note="note1")
    cooklog2 = CookLog(user_id=other_user_2.id, dish_id=dish6.id, note="note2")
    cooklog3 = CookLog(user_id=other_user_1.id, dish_id=dish6.id, note="note3")
    cooklog4 = CookLog(user_id=other_user_2.id, dish_id=dish6.id, note="note4")
    cooklog5 = CookLog(user_id=other_user_1.id, dish_id=dish7.id, note="note5")
    cooklog6 = CookLog(user_id=other_user_2.id, dish_id=dish8.id, note="note6")
    cooklog7 = CookLog(user_id=other_user_1.id, dish_id=dish9.id, note="note7")

    db_session.add_all([cooklog1, cooklog2, cooklog3, cooklog4, cooklog5, cooklog6, cooklog7])
    db_session.commit()

    response = client.get("/recommend/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["dish"]["name"] == "dishF"
    assert len(data[0]["notes"]) == 3

    del app.dependency_overrides[get_current_user]


def test_get_recommendation_no_recommendations(client: TestClient, db_session: Session, test_user: User):
    """
    Test getting dish recommendations when none are available.
    """

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    dish1 = Dish(name="dishA")
    db_session.add(dish1)
    db_session.commit()

    cooklog = CookLog(user_id=test_user.id, dish_id=dish1.id)
    db_session.add(cooklog)
    db_session.commit()

    response = client.get("/recommend/")
    assert response.status_code == 404

    del app.dependency_overrides[get_current_user]
