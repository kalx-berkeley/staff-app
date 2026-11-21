"""
Whether a staff member is old enough for a 21+ show, judged by their birth year.

Airtable's "Birth year" (`Staff.birth_year`) is all the app knows of a staff
member's age. Someone born in year Y is Y's-show-year minus Y on their
birthday, and a year younger before it, so for a 21+ show on date D:

- D.year - Y < 21: they must be under 21 on D, so they can't get a pass.
- D.year - Y == 21: they're under 21 on D if their birthday falls after it,
  so they're warned to make sure they're 21 by then.
- D.year - Y > 21, or no birth year: no check.

A multi-day show is judged by its first day. Birth years are private: callers
send only the result (`UNDER_21` or `MAYBE_UNDER_21`), never the year.
"""

from datetime import date
from typing import Literal

from fastapi import HTTPException, status

from app.models.show import Show
from app.models.staff import Staff

UNDER_21 = "under_21"
MAYBE_UNDER_21 = "maybe_under_21"
AgeCheck = Literal["under_21", "maybe_under_21"]

AGE_21_PLUS = "21+"

# For staff who might be under 21 on the date of a 21+ show they have a pass for
MAYBE_UNDER_21_WARNING = (
    "This show is 21+. Please make sure you'll be 21 or over on the show date:"
    " the venue will check your ID."
)


def _format_date(day: date) -> str:
    return f"{day:%b} {day.day}, {day.year}"


def first_show_day(show: Show) -> date:
    """The show's first day: its start date for a multi-day show, else its date."""
    return show.show_start_date or show.show_date


def check(show: Show, staff: Staff | None) -> AgeCheck | None:
    """
    Whether *staff* is, or might be, too young for *show*.

    :returns: `UNDER_21`, `MAYBE_UNDER_21`, or None when the show isn't 21+,
        the staff member has no birth year, or they're 21 or over.
    """
    if show.age_restriction != AGE_21_PLUS or staff is None or staff.birth_year is None:
        return None
    age_at_most = first_show_day(show).year - staff.birth_year
    if age_at_most < 21:
        return UNDER_21
    if age_at_most == 21:
        return MAYBE_UNDER_21
    return None


def ensure_not_under_21(show: Show, staff: Staff, *, you: bool = True) -> None:
    """
    Refuse a pass to a 21+ show to someone who must be under 21 on its date.

    Used wherever a staff member gets a staff or tabler pass: a direct claim, a
    lottery entry, joining the alternate list, and promotions assigning a
    tabler pass.

    :param show: The show.
    :param staff: The staff member who would get the pass.
    :param you: Whether *staff* is asking for themselves (sets the wording).
    :raises HTTPException: 409 if their birth year rules out being 21 on the show date.
    """
    if check(show, staff) != UNDER_21:
        return
    when = _format_date(first_show_day(show))
    if you:
        detail = (
            "This show is 21+. Going by the birth year in your staff record, you'll"
            f" be under 21 on {when}, so you can't get a pass for it."
        )
    else:
        detail = (
            "This show is 21+. Going by the birth year in their staff record,"
            f" {staff.name} will be under 21 on {when}, so they can't get a pass for it."
        )
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
