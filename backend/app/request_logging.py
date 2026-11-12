"""
Show who made each request on the backend's log lines.

Uvicorn's access lines and the app's own log lines both name the signed-in
user and their IP address, like ``someone@berkeley.edu (203.0.113.5)``. Guests on the
DJ studio and station office networks reach the backend without a login, so
they show as ``not-logged-in (203.0.113.5)``, or as ``DJ "Name" (203.0.113.5)``
when the pass giveaway's DJ Name box has a name in it (the frontend sends it in
the X-DJ-Name header, URL-encoded). Lines logged outside a request, such as the
scheduler's, stay as they are.

The user is always the real signed-in user, never anyone they are impersonating,
because Apache sets X-Forwarded-User from the OIDC login. The DJ name is only
what was typed into the box, so it's used only when nobody is signed in, and
only ever as a label on log lines.
"""

import logging
from contextvars import ContextVar
from typing import Any
from urllib.parse import unquote

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

NOT_LOGGED_IN = "not-logged-in"
DJ_NAME_HEADER = "x-dj-name"
MAX_DJ_NAME_LENGTH = 60
APP_LOG_FORMAT = "%(levelname)s:%(name)s:%(request_user)s%(message)s"

_request_user: ContextVar[str | None] = ContextVar("request_user", default=None)


def guest_label(dj_name_header: str | None) -> str:
    """
    Name a request from someone who isn't signed in.

    The header is typed by whoever is at the DJ studio computer, so it's
    decoded, stripped of quotes and non-printable characters (so it can't fake
    or break a log line) and shortened.

    :param dj_name_header: The URL-encoded X-DJ-Name header, if sent.
    :type dj_name_header: str | None
    :returns: ``DJ "Name"`` when there's a usable name, otherwise ``not-logged-in``.
    :rtype: str
    """
    name = unquote(dj_name_header or "")
    name = "".join(c for c in name if c.isprintable() and c != '"')
    name = " ".join(name.split())[:MAX_DJ_NAME_LENGTH].strip()
    return f'DJ "{name}"' if name else NOT_LOGGED_IN


class RequestUserMiddleware:
    """Remember who made the current request, for the logging below."""

    def __init__(self, app: ASGIApp) -> None:
        """
        :param app: The ASGI app to wrap.
        :type app: ASGIApp
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Record the request's user and IP address, then run the request.

        The value is deliberately not reset afterwards. Uvicorn runs each request
        in its own task, so the value ends with the task and can't reach another
        request. Starlette sends the 500 for an unhandled exception from outside
        this middleware, and that response's access line still needs the value.

        :param scope: The ASGI connection scope.
        :type scope: Scope
        :param receive: The ASGI receive callable.
        :type receive: Receive
        :param send: The ASGI send callable.
        :type send: Send
        """
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            user = headers.get("x-forwarded-user") or guest_label(
                headers.get(DJ_NAME_HEADER)
            )
            client = scope.get("client")
            ip_address = client[0] if client else "unknown IP"
            _request_user.set(f"{user} ({ip_address})")
        await self.app(scope, receive, send)


class AccessLogUserFilter(logging.Filter):
    """Replace the client address on uvicorn's access lines with the user and IP."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Rewrite the first log argument, which uvicorn fills with the client address.

        :param record: The access log record.
        :type record: logging.LogRecord
        :returns: True, because every access line should still be logged.
        :rtype: bool
        """
        user = _request_user.get()
        if user and isinstance(record.args, tuple) and record.args:
            record.args = (user, *record.args[1:])
        return True


def configure_request_logging() -> None:
    """
    Add the current request's user to log lines.

    Every log record gets a ``request_user`` attribute, which ``APP_LOG_FORMAT``
    prints. Uvicorn sets up its loggers before it imports the app, so the access
    filter added here stays in place.
    """
    make_record = logging.getLogRecordFactory()

    def make_record_with_user(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = make_record(*args, **kwargs)
        user = _request_user.get()
        record.request_user = f"[{user}] " if user else ""
        return record

    logging.setLogRecordFactory(make_record_with_user)
    logging.getLogger("uvicorn.access").addFilter(AccessLogUserFilter())
