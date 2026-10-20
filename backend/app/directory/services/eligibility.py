"""
The Sublist DJ requirements on the Staff Directory's profile page.

Everything here is a pure function of data already loaded, so the rules can
be tested without a database. See docs/directory/specs/profile-page/plan.md.

The requirements:
- Sublist DJ: the "Sublist DJ" status.
- Not on leave: no leave of absence today, and no "On leave" status.
- Shift: a qualifying shift in the previous complete quarter. Quarters are
  offset by a month (Feb–Apr, May–Jul, Aug–Oct, Nov–Jan). A shift is one or
  more back-to-back playlists under the person's own personas, and qualifies
  at 90 minutes or more. Automated playlists (roboshows) and specialty shows
  don't count. Placeholder personas are never anyone's own.
- Workforms: at least REQUIRED_MONTHLY_HOURS in each of the last 3 complete
  months. The older two count approved hours; the most recent one counts
  submitted hours that no department has denied, since decisions can take
  weeks. A month overlapping a leave of absence counts as met.
- DJ Quiz: the current quiz year's quiz. Until a year's deadline passes (the
  end of that day, Pacific time), last year's quiz still counts.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Set
from zoneinfo import ZoneInfo

from app.common.services.profile_providers import MonthHours

PACIFIC = ZoneInfo("America/Los_Angeles")
SUBLIST_DJ_STATUS = "Sublist DJ"
ON_LEAVE_STATUS = "on leave"
MIN_SHIFT_MINUTES = 90
REQUIRED_MONTHLY_HOURS = 6.0
WORKFORM_MONTHS = 3

_MONTH_ABBR = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip


# --- Months and quarters ---------------------------------------------------


def add_months(month: date, n: int) -> date:
    """The first day of the month *n* months after *month*'s (n may be negative)."""
    index = month.year * 12 + month.month - 1 + n
    return date(index // 12, index % 12 + 1, 1)


def quarter_start(day: date) -> date:
    """The first day of the KALX quarter *day* is in (Feb, May, Aug or Nov 1)."""
    # Months since the quarter started: Feb → 0, Mar → 1, Apr → 2, ..., Jan → 2
    offset = (day.month - 2) % 3
    return add_months(date(day.year, day.month, 1), -offset)


def quarter_end(start: date) -> date:
    """The last day of the quarter starting on *start*."""
    return add_months(start, 3) - timedelta(days=1)


def quarter_label(start: date) -> str:
    """For example "May–Jul 2026" or "Nov 2026–Jan 2027"."""
    last = add_months(start, 2)
    if last.year == start.year:
        return f"{_MONTH_ABBR[start.month - 1]}–{_MONTH_ABBR[last.month - 1]} {start.year}"
    return (
        f"{_MONTH_ABBR[start.month - 1]} {start.year}–"
        f"{_MONTH_ABBR[last.month - 1]} {last.year}"
    )


def month_name(month: date) -> str:
    return _MONTH_NAMES[month.month - 1]


def format_day(day: date) -> str:
    """For example "Oct 3, 2026"."""
    return f"{_MONTH_ABBR[day.month - 1]} {day.day}, {day.year}"


def format_hours(hours: float) -> str:
    """6.0 → "6", 4.5 → "4.5", 4.25 → "4.25"."""
    return f"{hours:g}"


def format_minutes(minutes: int) -> str:
    """135 → "2 h 15 min", 60 → "1 h", 45 → "45 min"."""
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} h {mins} min"
    return f"{hours} h" if hours else f"{mins} min"


# --- Shifts ----------------------------------------------------------------


@dataclass
class Playlist:
    """An aired Spinitron playlist (see DjShiftPlaylist)."""

    id: int
    persona_id: Optional[int]
    show_id: Optional[int]
    start: datetime
    end: datetime
    title: Optional[str] = None
    automation: bool = False


@dataclass
class PlaylistCheck:
    """One of the person's playlists, and whether it counted toward a shift."""

    playlist: Playlist
    # The shift (back-to-back playlists) it's part of, or None if it can't be
    # part of one
    shift_minutes: Optional[int]
    counted: bool
    # Why it didn't count: "automated", "specialty" or "too_short"
    reason: Optional[str] = None
    specialty_show: bool = False


@dataclass
class Shift:
    """Back-to-back playlists that make up one block of airtime."""

    playlists: List[Playlist]

    @property
    def start(self) -> datetime:
        return self.playlists[0].start

    @property
    def end(self) -> datetime:
        return self.playlists[-1].end

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    @property
    def qualifies(self) -> bool:
        return self.minutes >= MIN_SHIFT_MINUTES

    @property
    def quarter(self) -> date:
        return quarter_start(self.start.astimezone(PACIFIC).date())

    @property
    def title(self) -> Optional[str]:
        titles = []
        for playlist in self.playlists:
            if playlist.title and playlist.title not in titles:
                titles.append(playlist.title)
        return " / ".join(titles) or None


def own_playlists(
    playlists: Iterable[Playlist], persona_ids: Iterable[int], placeholder_ids: Set[int]
) -> List[Playlist]:
    """The playlists under the person's own personas, oldest first."""
    own = set(persona_ids) - placeholder_ids
    return sorted(
        (p for p in playlists if p.persona_id in own), key=lambda p: (p.start, p.id)
    )


def find_shifts(
    playlists: List[Playlist], specialty_show_ids: Set[int]
) -> tuple[List[Shift], List[PlaylistCheck]]:
    """
    Merge a person's playlists into shifts and say which count.

    Automated playlists and specialty shows are left out and never join a
    merge, so an automated hour can't stretch a live hour past 90 minutes.
    Two playlists are back to back when one ends exactly when the next starts.

    :param playlists: The person's own playlists, oldest first (see `own_playlists`).
    :param specialty_show_ids: Spinitron show IDs of specialty shows.
    :returns: The shifts, and a check for every playlist, both oldest first.
    """
    shifts: List[Shift] = []
    excluded: Dict[int, str] = {}
    for playlist in playlists:
        if playlist.automation:
            excluded[playlist.id] = "automated"
        elif playlist.show_id is not None and playlist.show_id in specialty_show_ids:
            excluded[playlist.id] = "specialty"
        elif shifts and shifts[-1].end == playlist.start:
            shifts[-1].playlists.append(playlist)
        else:
            shifts.append(Shift(playlists=[playlist]))
    shift_of = {p.id: shift for shift in shifts for p in shift.playlists}
    checks = []
    for playlist in playlists:
        reason = excluded.get(playlist.id)
        shift = shift_of.get(playlist.id)
        if shift is not None and not shift.qualifies:
            reason = "too_short"
        checks.append(
            PlaylistCheck(
                playlist=playlist,
                shift_minutes=shift.minutes if shift else None,
                counted=reason is None,
                reason=reason,
                specialty_show=excluded.get(playlist.id) == "specialty",
            )
        )
    return shifts, checks


# --- Workforms -------------------------------------------------------------


@dataclass
class DepartmentCheck:
    department: str
    hours: float
    decision: Optional[str]
    counted: bool


@dataclass
class MonthCheck:
    month: date
    most_recent: bool
    met: bool
    counted_hours: float
    status: str
    loa: bool
    departments: List[DepartmentCheck] = field(default_factory=list)
    # Departments that haven't decided, in an older month (their hours don't
    # count until they approve them)
    pending_departments: List[str] = field(default_factory=list)


def workform_months(today: date) -> List[date]:
    """The last WORKFORM_MONTHS complete months, most recent first."""
    this_month = date(today.year, today.month, 1)
    return [add_months(this_month, -n) for n in range(1, WORKFORM_MONTHS + 1)]


def check_month(month_hours: MonthHours, most_recent: bool) -> MonthCheck:
    """Whether one month's workform meets the hours minimum."""
    submitted = month_hours.status in ("submitted", "locked")
    departments = []
    for block in month_hours.departments:
        if most_recent:
            counted = submitted and block.decision != "Denied"
        else:
            counted = block.decision == "Approved"
        departments.append(
            DepartmentCheck(
                department=block.department,
                hours=block.hours,
                decision=block.decision,
                counted=counted,
            )
        )
    counted_hours = sum(d.hours for d in departments if d.counted)
    pending = (
        []
        if most_recent
        else [d.department for d in departments if d.decision is None and d.hours > 0]
    )
    return MonthCheck(
        month=month_hours.month,
        most_recent=most_recent,
        met=month_hours.loa_overlaps_month or counted_hours >= REQUIRED_MONTHLY_HOURS,
        counted_hours=counted_hours,
        status=month_hours.status,
        loa=month_hours.loa_overlaps_month,
        departments=departments,
        pending_departments=pending,
    )


def month_summary(check: MonthCheck) -> str:
    """For example "Aug 4.5 h ✗" or "Jul LOA ✓"."""
    mark = "✓" if check.met else "✗"
    abbr = _MONTH_ABBR[check.month.month - 1]
    if check.loa:
        return f"{abbr} LOA {mark}"
    return f"{abbr} {format_hours(check.counted_hours)} h {mark}"


# --- DJ Quiz ---------------------------------------------------------------


@dataclass
class QuizCheck:
    met: bool
    current_year: int
    years: List[int]
    # This year's deadline, if one is set
    this_year_deadline: Optional[date]
    # Set when this year's quiz is due and not yet done
    due: Optional[date]
    deadline_announced: bool


def check_quiz(years: List[int], deadlines: Dict[int, date], today: date) -> QuizCheck:
    """
    Whether the person has done the current quiz year's DJ Quiz.

    The current quiz year is this year once this year's deadline has passed,
    and last year until then (or while this year has no deadline).
    """
    this_year = today.year
    deadline = deadlines.get(this_year)
    current_year = this_year if deadline is not None and today > deadline else this_year - 1
    due = (
        deadline
        if deadline is not None and today <= deadline and this_year not in years
        else None
    )
    return QuizCheck(
        # Doing this year's quiz early also covers the rest of last year's
        met=any(year >= current_year for year in years),
        current_year=current_year,
        years=sorted(years),
        this_year_deadline=deadline,
        due=due,
        deadline_announced=deadline is not None,
    )


# --- Eligible until --------------------------------------------------------


def eligible_until(
    today: date,
    shifts: List[Shift],
    quiz: QuizCheck,
    loa_start: Optional[date],
) -> date:
    """
    The last day someone who's eligible today stays eligible, as far as is
    known now (the workforms requirement isn't counted, since it depends on
    hours not yet reported).

    The earliest of: the end of the quarter their latest qualifying shift
    covers (a shift in one quarter covers the next), this year's quiz
    deadline if this year's quiz isn't done, and the day before an upcoming
    leave.
    """
    current = quarter_start(today)
    covered_until = quarter_end(current)
    if any(s.qualifies and s.quarter == current for s in shifts):
        covered_until = quarter_end(add_months(current, 3))
    candidates = [covered_until]
    if quiz.due is not None:
        candidates.append(quiz.due)
    if loa_start is not None and loa_start > today:
        candidates.append(loa_start - timedelta(days=1))
    return min(candidates)


def next_workform_note(today: date) -> str:
    """Which month's workform counts toward the requirement next, and when."""
    this_month = date(today.year, today.month, 1)
    next_month = add_months(this_month, 1)
    return (
        f"Keep reporting {format_hours(REQUIRED_MONTHLY_HOURS)} h a month: "
        f"{month_name(this_month)}'s workform counts from "
        f"{month_name(next_month)} 1."
    )
