"""Flag workform hours that may have been worked during a leave of absence.

A leave runs from its start through its end, both inclusive. Either may be
blank: a start alone is open-ended, an end alone means on leave until then,
and neither means no leave (see app/common/services/leave_service.py).
"""

from datetime import date
from typing import Optional

from app.workforms.services.months import last_day_of_month

# A dated entry falls inside the leave
INSIDE = "inside"
# An undated entry is in a month that the leave overlaps
MAY_OVERLAP = "may_overlap"


def _overlaps(
    loa_start: Optional[date], loa_end: Optional[date], first: date, last: date
) -> bool:
    if loa_start is None and loa_end is None:
        return False
    return (loa_start is None or loa_start <= last) and (
        loa_end is None or loa_end >= first
    )


def entry_flag(
    work_date: Optional[date],
    month: date,
    loa_start: Optional[date],
    loa_end: Optional[date],
) -> Optional[str]:
    """
    How an entry relates to a leave of absence.

    :returns: INSIDE for a dated entry during the leave, MAY_OVERLAP for an
        undated entry in a month the leave overlaps, else None
    """
    if work_date is not None:
        return INSIDE if _overlaps(loa_start, loa_end, work_date, work_date) else None
    return (
        MAY_OVERLAP
        if _overlaps(loa_start, loa_end, month, last_day_of_month(month))
        else None
    )


def month_overlaps(month: date, loa_start: Optional[date], loa_end: Optional[date]) -> bool:
    """Whether a leave overlaps any day of *month*."""
    return _overlaps(loa_start, loa_end, month, last_day_of_month(month))
