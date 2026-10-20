"""
Data the Staff Directory's profile page needs from other sub-sites.

Sub-sites never import each other, so the sub-site that owns the data
registers a provider here from `main.py`, and the directory calls it through
this module. A provider that isn't registered (for example while KALX
Workforms is turned off) makes the directory show that part as unavailable.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Literal, Optional, Set

from sqlalchemy.orm import Session

from app.models.staff import Staff


@dataclass
class DepartmentHours:
    """One department's block of a submitted workform."""

    department: str
    hours: float
    # "Approved", "Denied", or None while the department hasn't decided
    decision: Optional[str] = None


@dataclass
class MonthHours:
    """One person's workform for one month."""

    month: date
    # "not_started": nothing saved or submitted; "draft": saved, not
    # submitted; "submitted": submitted, no department has decided yet;
    # "locked": a department has decided
    status: Literal["not_started", "draft", "submitted", "locked"]
    # Hours reported in the draft or the submission
    reported_hours: float = 0.0
    # The submitted blocks, empty unless submitted
    departments: List[DepartmentHours] = field(default_factory=list)
    is_late: bool = False
    # A leave of absence overlaps the month, so the hours minimum doesn't apply
    loa_overlaps_month: bool = False


# Spinitron show IDs of every specialty show that isn't deleted (retired ones
# included)
SpecialtyShowIdsProvider = Callable[[Session], Set[int]]
# One person's workforms for the given months, keyed by month (first day)
MonthlyHoursProvider = Callable[[Session, Staff, List[date]], Dict[date, MonthHours]]

_specialty_show_ids_provider: Optional[SpecialtyShowIdsProvider] = None
_monthly_hours_provider: Optional[MonthlyHoursProvider] = None


def register_specialty_show_ids_provider(provider: SpecialtyShowIdsProvider) -> None:
    """Register the function that lists specialty shows' Spinitron show IDs."""
    global _specialty_show_ids_provider
    _specialty_show_ids_provider = provider


def register_monthly_hours_provider(provider: MonthlyHoursProvider) -> None:
    """Register the function that returns a person's workforms by month."""
    global _monthly_hours_provider
    _monthly_hours_provider = provider


def specialty_show_ids(db: Session) -> Optional[Set[int]]:
    """Specialty shows' Spinitron show IDs, or None if no provider is registered."""
    if _specialty_show_ids_provider is None:
        return None
    return _specialty_show_ids_provider(db)


def monthly_hours(
    db: Session, staff: Staff, months: List[date]
) -> Optional[Dict[date, MonthHours]]:
    """A person's workforms for *months*, or None if no provider is registered."""
    if _monthly_hours_provider is None:
        return None
    return _monthly_hours_provider(db, staff, months)
