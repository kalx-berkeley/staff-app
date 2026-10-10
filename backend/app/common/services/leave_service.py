"""Leave of absence: when a staff member is on leave, from Airtable's LOA dates.

A leave runs from Staff.loa_start through Staff.loa_end, both inclusive. Either
may be blank: a start alone is open-ended, an end alone means on leave until
then, and neither means no leave. Dates are Pacific, like the rest of the app.
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.models.show import Show
from app.models.staff import Staff

_LA = ZoneInfo("America/Los_Angeles")


def today_pt() -> date:
    """Return today's date in Pacific time."""
    return datetime.now(_LA).date()


def has_leave(staff: Staff) -> bool:
    """Return True if the staff member has a leave of absence on record."""
    return staff.loa_start is not None or staff.loa_end is not None


def on_leave(staff: Staff, day: date) -> bool:
    """
    Return True if *day* falls within the staff member's leave of absence.

    :param staff: The staff member.
    :param day: The date to check.
    """
    if not has_leave(staff):
        return False
    if staff.loa_start is not None and day < staff.loa_start:
        return False
    if staff.loa_end is not None and day > staff.loa_end:
        return False
    return True


def leave_covers_show(staff: Staff, show: Show) -> bool:
    """
    Return True if the staff member is on leave for every day of *show*.

    A multi-day show runs from show_start_date through show_date. A leave is a
    single unbroken range, so it covers the show if it covers both ends.

    :param staff: The staff member.
    :param show: The show.
    """
    first_day = show.show_start_date or show.show_date
    return on_leave(staff, first_day) and on_leave(staff, show.show_date)


def leave_is_current_or_upcoming(staff: Staff, today: Optional[date] = None) -> bool:
    """
    Return True if the staff member's leave hasn't ended yet.

    :param staff: The staff member.
    :param today: The current date; defaults to today in Pacific time.
    """
    if not has_leave(staff):
        return False
    return staff.loa_end is None or staff.loa_end >= (today or today_pt())


def _format_date(day: date) -> str:
    return f"{day:%b} {day.day}, {day.year}"


def format_leave(staff: Staff) -> str:
    """
    Describe the staff member's leave dates, e.g. "Mar 1, 2027 – Jun 1, 2027".

    :param staff: The staff member, who must have a leave on record.
    :returns: The range, or "from <start>" / "until <end>" for a one-sided leave.
    """
    if staff.loa_start is not None and staff.loa_end is not None:
        return f"{_format_date(staff.loa_start)} – {_format_date(staff.loa_end)}"
    if staff.loa_start is not None:
        return f"from {_format_date(staff.loa_start)}"
    return f"until {_format_date(staff.loa_end)}"


def ensure_not_on_leave_for_show(staff: Staff, show: Show) -> None:
    """
    Refuse a staff pass to someone on leave for every day of *show*.

    Used wherever a staff member gets a staff pass for themselves: a direct
    claim, a lottery entry, or joining the alternate queue.

    :param staff: The staff member asking for a pass.
    :param show: The show.
    :raises HTTPException: 409 if the staff member's leave covers the show.
    """
    if leave_covers_show(staff, show):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You're on leave of absence {format_leave(staff)}, so you can't"
                " claim passes for this show."
            ),
        )
