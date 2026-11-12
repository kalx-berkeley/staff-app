"""
Showing datetimes to people, always in Pacific time.

The database stores datetimes as UTC, and SQLite hands them back without a
time zone. Never put a datetime straight into an email or other text (an
f-string prints it as UTC, down to the microsecond). Format it with
:func:`format_pacific_datetime` instead.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


def as_utc(dt: datetime) -> datetime:
    """Return *dt* as an aware datetime, treating a naive one as UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def to_pacific(dt: datetime) -> datetime:
    """Return *dt* in Pacific time, treating a naive one as UTC."""
    return as_utc(dt).astimezone(PACIFIC)


def format_pacific_datetime(dt: datetime) -> str:
    """
    Format *dt* for people, in Pacific time, to the minute.

    :param dt: An aware datetime, or a naive one in UTC.
    :returns: For example "Thu, Nov 12, 2026 at 3:05pm".
    """
    local = to_pacific(dt)
    hour = local.hour % 12 or 12
    period = "am" if local.hour < 12 else "pm"
    return f"{local:%a, %b} {local.day}, {local.year} at {hour}:{local:%M}{period}"
