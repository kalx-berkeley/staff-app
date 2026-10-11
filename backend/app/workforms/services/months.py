"""Workform months, deadlines and lateness, in Pacific time."""

import calendar
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.config import settings

PACIFIC = ZoneInfo("America/Los_Angeles")


def today_pacific() -> date:
    return datetime.now(PACIFIC).date()


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def previous_month(month: date) -> date:
    return (
        date(month.year - 1, 12, 1)
        if month.month == 1
        else date(month.year, month.month - 1, 1)
    )


def next_month(month: date) -> date:
    return (
        date(month.year + 1, 1, 1)
        if month.month == 12
        else date(month.year, month.month + 1, 1)
    )


def last_day_of_month(month: date) -> date:
    return month.replace(day=calendar.monthrange(month.year, month.month)[1])


def open_months(today: date | None = None) -> list[date]:
    """
    The months a staff member can add to and submit, newest first.

    The current month is open, and so is last month: it can still be
    submitted after its deadline, but is then late.
    """
    current = first_of_month(today or today_pacific())
    return [current, previous_month(current)]


def deadline(month: date) -> datetime:
    """The end of the deadline day of the following month, Pacific time, as aware UTC."""
    due = next_month(month).replace(day=settings.workforms_deadline_day)
    return datetime.combine(due, time(23, 59, 59), PACIFIC).astimezone(timezone.utc)


def is_late(month: date, submitted_at: datetime) -> bool:
    """
    Whether a submission at *submitted_at* is after *month*'s deadline.

    A naive *submitted_at* is taken as UTC, which is how the database stores
    datetimes.
    """
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=timezone.utc)
    return submitted_at > deadline(month)


def parse_month(value: str) -> date:
    """
    Parse a "YYYY-MM" month.

    :raises ValueError: If *value* isn't a valid month
    """
    year, _, month = value.partition("-")
    if len(year) != 4 or len(month) != 2 or not (year + month).isdigit():
        raise ValueError(f"Invalid month {value!r}; expected YYYY-MM")
    return date(int(year), int(month), 1)


def format_month(month: date) -> str:
    return month.strftime("%Y-%m")
