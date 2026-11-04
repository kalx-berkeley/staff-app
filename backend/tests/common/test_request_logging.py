"""Tests for the user and IP address shown on the backend's log lines."""

import asyncio
import logging
import os
import subprocess
import sys

import pytest
from fastapi import FastAPI

from app.main import app as real_app
from app.request_logging import APP_LOG_FORMAT, RequestUserMiddleware

app_logger = logging.getLogger("app.test_request_logging")
access_logger = logging.getLogger("uvicorn.access")

EMAIL = "someone@berkeley.edu"
IP_ADDRESS = "203.0.113.5"


def make_app() -> FastAPI:
    """
    Build a small app with sync, async and failing routes behind the middleware.

    :returns: The app.
    :rtype: FastAPI
    """
    app = FastAPI()
    app.add_middleware(RequestUserMiddleware)

    @app.get("/sync")
    def sync_route() -> dict:
        app_logger.info("in sync route")
        return {}

    @app.get("/async")
    async def async_route() -> dict:
        app_logger.info("in async route")
        return {}

    @app.get("/fails")
    async def failing_route() -> dict:
        raise RuntimeError("unhandled")

    return app


def run_request(path: str, email: str | None = None) -> None:
    """
    Run one request the way uvicorn does, logging its access line from send().

    :param path: The path to request.
    :type path: str
    :param email: The X-Forwarded-User value, or None for a guest.
    :type email: str | None
    """
    headers = [(b"x-forwarded-user", email.encode())] if email else []
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": headers,
        "client": (IP_ADDRESS, 0),
        "server": ("127.0.0.1", 8420),
    }

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        if message["type"] == "http.response.start":
            access_logger.info(
                '%s - "%s %s HTTP/%s" %d',
                f"{IP_ADDRESS}:0",
                "GET",
                path,
                "1.1",
                message["status"],
            )

    async def run() -> None:
        try:
            await make_app()(scope, receive, send)
        except RuntimeError:
            pass  # Starlette re-raises after sending the 500, for uvicorn to log

    asyncio.run(run())


def access_line(caplog: pytest.LogCaptureFixture) -> str:
    """
    Return the one access line the request logged.

    :param caplog: The pytest log capture.
    :type caplog: pytest.LogCaptureFixture
    :returns: The formatted line.
    :rtype: str
    """
    lines = [r.getMessage() for r in caplog.records if r.name == access_logger.name]
    assert len(lines) == 1
    return lines[0]


@pytest.fixture(autouse=True)
def capture_info(caplog: pytest.LogCaptureFixture) -> None:
    """Capture INFO lines, which are below the default level in tests."""
    caplog.set_level(logging.INFO)


def test_access_line_shows_email_and_ip(caplog):
    run_request("/async", EMAIL)
    assert access_line(caplog).startswith(f'{EMAIL} ({IP_ADDRESS}) - "GET /async')


def test_access_line_marks_guest_as_not_logged_in(caplog):
    run_request("/async")
    assert access_line(caplog).startswith(f'not-logged-in ({IP_ADDRESS}) - "GET')


def test_access_line_of_unhandled_error_shows_user(caplog):
    run_request("/fails", EMAIL)
    line = access_line(caplog)
    assert line.startswith(f"{EMAIL} ({IP_ADDRESS})")
    assert line.endswith("500")


@pytest.mark.parametrize("path", ["/sync", "/async"])
def test_app_line_shows_user(caplog, path):
    """Sync routes run in a worker thread, so both kinds of route are covered."""
    run_request(path, EMAIL)
    record = next(r for r in caplog.records if r.name == app_logger.name)
    assert record.request_user == f"[{EMAIL} ({IP_ADDRESS})] "


def test_app_line_marks_guest_as_not_logged_in(caplog):
    run_request("/async")
    record = next(r for r in caplog.records if r.name == app_logger.name)
    assert record.request_user == f"[not-logged-in ({IP_ADDRESS})] "


def test_line_outside_a_request_has_no_user(caplog):
    run_request("/async", EMAIL)
    app_logger.info("from the scheduler")
    assert caplog.records[-1].request_user == ""
    formatted = logging.Formatter(APP_LOG_FORMAT).format(caplog.records[-1])
    assert formatted == f"INFO:{app_logger.name}:from the scheduler"


def test_real_app_uses_the_middleware():
    assert any(m.cls is RequestUserMiddleware for m in real_app.user_middleware)


def test_real_app_logs_with_the_user_format():
    """
    Check the root handler in a clean process, because pytest adds its own handlers.

    A library calling basicConfig on import would otherwise leave main.py's format
    unused, and app lines would silently lose the user.
    """
    code = "import logging, app.main\nprint(logging.getLogger().handlers[0].formatter._fmt)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "DATABASE_URL": "sqlite:///:memory:"},
    )
    assert result.stdout.strip() == APP_LOG_FORMAT
