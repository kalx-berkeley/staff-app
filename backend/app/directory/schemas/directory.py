"""Pydantic schemas for the Staff Directory API."""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class DjPersona(BaseModel):
    """One of a staff member's Spinitron DJ personas."""

    id: int
    name: str


class DirectoryEntry(BaseModel):
    """One active staff member in the Staff Directory."""

    id: int
    name: str
    pronouns: str | None = None
    email: str
    phone: str
    # Spinitron persona names joined with commas, and each persona on its own
    dj_name: str | None = None
    dj_personas: list[DjPersona] = []
    departments: list[str] = []
    statuses: list[str] = []
    titles_and_roles: str | None = None
    # Changes whenever the photo does, for cache-busting the photo URL; None
    # when the staff member has no photo.
    photo_version: str | None = None
    # Leave of absence that hasn't ended yet (None once it's past); either
    # date may be None for a one-sided leave. on_leave is True during it.
    on_leave: bool = False
    loa_start: date | None = None
    loa_end: date | None = None
    # The years whose DJ Quiz the staff member has completed
    dj_quiz_years: list[int] = []


# --- Profile page ----------------------------------------------------------


class Check(BaseModel):
    """One Sublist DJ requirement. met is None when it can't be checked."""

    met: Optional[bool]
    summary: str


class LeaveCheck(Check):
    loa_start: Optional[date] = None
    loa_end: Optional[date] = None


class PlaylistCheckResponse(BaseModel):
    id: int
    start: datetime
    end: datetime
    title: Optional[str] = None
    minutes: int
    # The length of the back-to-back block it's part of, if any
    shift_minutes: Optional[int] = None
    counted: bool
    reason: Optional[Literal["automated", "specialty", "too_short"]] = None
    quarter: Literal["previous", "current"]
    url: str


class ShiftCheck(Check):
    previous_quarter: str
    current_quarter: str
    min_minutes: int
    playlists: List[PlaylistCheckResponse] = []
    shifts_as_of: Optional[datetime] = None


class DepartmentCheckResponse(BaseModel):
    department: str
    hours: float
    decision: Optional[str] = None
    counted: bool


class MonthCheckResponse(BaseModel):
    month: str  # "YYYY-MM"
    most_recent: bool
    met: bool
    counted_hours: float
    status: str
    loa: bool
    departments: List[DepartmentCheckResponse] = []
    pending_departments: List[str] = []


class WorkformsCheck(Check):
    required_hours: float
    months: List[MonthCheckResponse] = []


class QuizCheckResponse(Check):
    current_year: int
    years: List[int] = []
    this_year_deadline: Optional[date] = None
    due: Optional[date] = None
    deadline_announced: bool


class EligibilityResponse(BaseModel):
    """The Sublist DJ requirements, for someone with a persona or the Sublist DJ status."""

    eligible: bool
    unmet: int
    unavailable: int
    eligible_until: Optional[date] = None
    next_workform_note: str
    sublist: Check
    leave: LeaveCheck
    shift: ShiftCheck
    workforms: WorkformsCheck
    quiz: QuizCheckResponse


class WorkformMonth(BaseModel):
    """One row of the profile's workforms summary."""

    month: str  # "YYYY-MM"
    status: Literal["not_started", "draft", "submitted", "locked"]
    reported_hours: float
    approved_hours: float
    is_late: bool
    loa: bool


class ProfileResponse(BaseModel):
    """A staff member's profile page, shown to them and to site admins."""

    entry: DirectoryEntry
    # The editable values as Airtable holds them
    first_name: Optional[str] = None
    surname: Optional[str] = None
    # Every leave on record, including one that has ended
    loa_start: Optional[date] = None
    loa_end: Optional[date] = None
    is_self: bool
    # Whether the viewer can save changes (editing is on, and they're this
    # person or Paid Staff)
    can_edit: bool
    # None unless the person has a Spinitron persona or the Sublist DJ status
    eligibility: Optional[EligibilityResponse] = None
    # The last 12 months, most recent first; None when workforms aren't available
    workforms: Optional[List[WorkformMonth]] = None


class ProfileUpdate(BaseModel):
    """New values for every editable field on the profile page."""

    first_name: str = Field(..., max_length=100)
    surname: Optional[str] = Field(None, max_length=100)
    pronouns: Optional[str] = Field(None, max_length=40)
    phone: Optional[str] = Field(None, max_length=40)
    # Spinitron persona IDs, in order
    dj_persona_ids: List[int] = []


class PersonaOption(BaseModel):
    """A Spinitron persona offered by the DJ Name editor."""

    id: int
    name: str


class PersonaResolveRequest(BaseModel):
    url: str = Field(..., max_length=500)


class DjQuizDeadlineItem(BaseModel):
    year: int
    deadline: date


class DjQuizDeadlineUpdate(BaseModel):
    deadline: date
