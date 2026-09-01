"""In-memory sliding-window rate limiter as a FastAPI dependency factory."""

import time
import threading
from collections import defaultdict, deque

from fastapi import Header, Request

_store: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


class RateLimitExceeded(Exception):
    """Raised when a client IP exceeds the configured request rate."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded; retry after {retry_after}s")


def _get_client_ip(request: Request, x_forwarded_for: str | None) -> str:
    """
    Return the best-available client IP.

    Prefers the first address in X-Forwarded-For (set by the reverse proxy)
    over the direct TCP connection host, which in a proxied setup is the
    proxy itself.

    :param request: Incoming FastAPI request.
    :param x_forwarded_for: Proxy-set header carrying the real client IP.
    :returns: IP address string.
    """
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _reset_for_testing() -> None:
    """Clear all rate-limit state. For use in tests only."""
    with _lock:
        _store.clear()


def create_rate_limit_dependency(max_requests: int, window_seconds: int):
    """
    Return a FastAPI dependency that enforces a per-IP sliding-window rate limit.

    The returned callable is used with ``Depends()``.  It raises
    ``RateLimitExceeded`` when a single IP exceeds *max_requests* within any
    rolling *window_seconds* period.  State is held in process memory only and
    is not persisted across restarts.

    :param max_requests: Maximum requests allowed within the window.
    :param window_seconds: Length of the sliding window in seconds.
    :returns: FastAPI dependency callable.
    """

    def check(
        request: Request,
        x_forwarded_for: str | None = Header(None, alias="X-Forwarded-For"),
    ) -> None:
        ip = _get_client_ip(request, x_forwarded_for)
        now = time.monotonic()
        cutoff = now - window_seconds

        with _lock:
            timestamps = _store[ip]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                # Time until the oldest slot leaves the window
                retry_after = max(1, int(timestamps[0] - cutoff) + 1)
                raise RateLimitExceeded(retry_after)

            timestamps.append(now)

    return check
