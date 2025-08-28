
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.models import User
from src.api.auth_utils import get_password_hash

def test_login_for_access_token(client: TestClient, db: Session):
    # Arrange: Create a user in the test database
    username = "testuser"
    password = "testpassword"
    hashed_password = get_password_hash(password)
    user = User(username=username, hashed_password=hashed_password, telegram_id=123)
    db.add(user)
    db.commit()

    # Act: Attempt to log in
    login_data = {"username": username, "password": password}
    response = client.post("/api/v1/auth/login", data=login_data)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_for_access_token_incorrect_password(client: TestClient, db: Session):
    # Arrange
    username = "testuser"
    password = "testpassword"
    hashed_password = get_password_hash(password)
    user = User(username=username, hashed_password=hashed_password, telegram_id=123)
    db.add(user)
    db.commit()

    # Act
    login_data = {"username": username, "password": "wrongpassword"}
    response = client.post("/api/v1/auth/login", data=login_data)

    # Assert
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

def test_read_users_me(authenticated_client: TestClient):
    # Act
    response = authenticated_client.get("/api/v1/auth/me")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Test Admin"
    assert data["email"] == "admin@test.com"
    assert data["avatar_initial"] == "T"


