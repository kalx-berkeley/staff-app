"""Shared test configuration and fixtures."""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Set before importing the app: app.config ignores .env when TESTING is set.
os.environ["TESTING"] = "1"
# The workforms sub-site is off by default; its tests need its routes
os.environ["WORKFORMS_ENABLED"] = "true"
# Likewise the directory sub-site
os.environ["DIRECTORY_ENABLED"] = "true"

from app.main import app  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.rate_limiter import _reset_for_testing  # noqa: E402

# Create a single test database engine that all tests will share
# Using StaticPool to ensure the in-memory database persists across connections
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Keep the same connection for all threads
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


class _BlockedSMTP:
    """Stands in for smtplib.SMTP so no test can reach a real mail server."""

    def __init__(self, *args, **kwargs):
        raise AssertionError(
            "A test tried to send real email over SMTP. Patch"
            " app.common.services.notification_service.send_email in the test."
        )


@pytest.fixture(autouse=True)
def block_real_email(monkeypatch):
    """
    Fail any test that would deliver real email.

    send_email delivers through the local mail server, so an unpatched send
    would land in the developer's postfix queue. Tests that patch smtplib.SMTP
    themselves still take precedence.
    """
    from app.common.services import notification_service

    monkeypatch.setattr(notification_service.smtplib, "SMTP", _BlockedSMTP)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate limiter state before each test."""
    _reset_for_testing()


@pytest.fixture(scope="function")
def db() -> Session:
    """
    Create a fresh database session for each test.
    The tables are created once per run and emptied after each test, which is
    much faster than creating and dropping all of them every time. Integer IDs
    still start at 1 in each test, since no table uses SQLite's AUTOINCREMENT.
    """
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        with engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())


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
