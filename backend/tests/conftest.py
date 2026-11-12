"""Shared test configuration and fixtures."""

import os
import re

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


# An ISO datetime with no "Z" or UTC offset. The frontend would read it as the
# viewer's local time, so every datetime the API sends must say it's UTC.
_NAIVE_DATETIME = re.compile(r'"(\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d+)?)?)"')


def _fail_on_naive_datetimes(response) -> None:
    """Fail the test if a JSON response holds a datetime without a time zone."""
    if "application/json" not in response.headers.get("content-type", ""):
        return
    response.read()
    match = _NAIVE_DATETIME.search(response.text)
    if match:
        raise AssertionError(
            f"{response.request.method} {response.request.url.path} returned the"
            f" datetime {match.group(1)} with no time zone. Type the field as"
            " app.common.schemas.types.UtcDatetime (or make the value aware) so"
            " the frontend doesn't read it as local time."
        )


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
def artist_info_warmups(monkeypatch) -> list[list[str]]:
    """
    Record, instead of running, the band popup's background artist info fetches.

    Saving a show with band tags queues `warm_artist_info`, which would call
    MusicBrainz, Wikidata and Wikipedia for real (and on the app's own
    database). Each queued call's artist IDs are appended to the returned list.
    """
    from app.pass_giveaway.services import artist_info_service

    calls: list[list[str]] = []
    monkeypatch.setattr(
        artist_info_service, "warm_artist_info", lambda ids: calls.append(list(ids))
    )
    return calls


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
        test_client.event_hooks["response"].append(_fail_on_naive_datetimes)
        yield test_client

    # Clean up the override after the test
    app.dependency_overrides.clear()
