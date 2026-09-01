"""Shared test configuration and fixtures."""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.rate_limiter import _reset_for_testing

# Set testing environment variable
os.environ["TESTING"] = "1"


# Create a single test database engine that all tests will share
# Using StaticPool to ensure the in-memory database persists across connections
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Keep the same connection for all threads
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate limiter state before each test."""
    _reset_for_testing()


@pytest.fixture(scope="function")
def db() -> Session:
    """
    Create a fresh database session for each test.
    Tables are created before the test and dropped after.
    """
    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create a new session for the test
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        # Drop all tables after the test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """
    Create a test client with the database dependency overridden.
    Each test gets a fresh client with its own database session.
    """

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up the override after the test
    app.dependency_overrides.clear()
