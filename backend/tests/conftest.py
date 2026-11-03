"""
Shared pytest fixtures and test database engine for backend API tests.
Ensures a single shared in-memory SQLite database across all test modules.
"""
import os
os.environ["MOCK_EMBEDDINGS"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.user import User

# Shared in-memory SQLite database with StaticPool for multi-threaded test requests
shared_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SharedTestingSessionLocal = sessionmaker(bind=shared_test_engine)


def override_get_db():
    db = SharedTestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def db_tables(monkeypatch):
    """Ensure database schema is created before each test and dropped after."""
    monkeypatch.setattr("app.tasks.video_tasks.SessionLocal", SharedTestingSessionLocal)
    Base.metadata.create_all(shared_test_engine)
    yield
    Base.metadata.drop_all(shared_test_engine)


@pytest.fixture
def default_admin_token(db_tables):
    """Seed a default active admin user for regression test suites."""
    db = SharedTestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == "test_admin@visiontrace.ai").first()
        if not user:
            user = User(
                email="test_admin@visiontrace.ai",
                hashed_password=get_password_hash("TestAdmin123!"),
                full_name="Regression Test Admin",
                role="admin",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token(user.id, role="admin", email=user.email)
        return token
    finally:
        db.close()


@pytest.fixture
def client(default_admin_token):
    """Shared TestClient for FastAPI endpoints with pre-authorized admin session."""
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {default_admin_token}"})
    return c
