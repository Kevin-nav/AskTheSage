import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from src.api.main import app
from src.api.dependencies import get_db
from src.models.models import Base, User
from src.api.auth_utils import get_password_hash

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create database tables before tests and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a new database session for each test, with a rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client that uses the test database session."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def authenticated_client(client: TestClient, db: Session) -> TestClient:
    """Create an authenticated test client."""
    test_username = "testadmin"
    test_password = "testpassword"
    hashed_password = get_password_hash(test_password)
    admin_user = User(
        username=test_username,
        hashed_password=hashed_password,
        full_name="Test Admin",
        email="admin@test.com",
        telegram_id=12345,
        is_admin=True
    )
    db.add(admin_user)
    db.commit()

    login_data = {"username": test_username, "password": test_password}
    response = client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"
    return client