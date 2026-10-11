"""KALX Workforms request and response schemas."""

from datetime import date, datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class EntryRequest(BaseModel):
    department: str
    hours: float
    description: str
    work_date: Optional[date] = None


class EntryResponse(BaseModel):
    id: int
    department: str
    hours: float
    description: str
    work_date: Optional[date] = None
    # "inside" (dated, during a leave) or "may_overlap" (undated, in a month a
    # leave overlaps)
    loa_flag: Optional[str] = None


class DepartmentsResponse(BaseModel):
    # The user's own departments first, then the rest, each sorted by name
    own: List[str]
    other: List[str]


class DepartmentResult(BaseModel):
    """A department's block of a submitted workform, as Airtable has it."""

    hours: Optional[float] = None
    description: Optional[str] = None
    decision: Optional[Literal["Approved", "Denied"]] = None


class WorkformResponse(BaseModel):
    month: str
    is_open: bool
    is_current_month: bool
    deadline: datetime
    # "not_started": nothing saved or submitted; "draft": entries saved, not
    # submitted; "submitted": submitted, can still be changed and resubmitted;
    # "locked": a department has decided, so it can't be changed
    status: Literal["not_started", "draft", "submitted", "locked"]
    has_unsent_changes: bool
    submitted_at: Optional[datetime] = None
    is_late: bool
    # True if submitting now would be after the deadline
    would_be_late: bool
    entries: List[EntryResponse]
    results: Dict[str, DepartmentResult] = Field(default_factory=dict)
    loa_start: Optional[date] = None
    loa_end: Optional[date] = None
    # True if a leave of absence overlaps the month, so the monthly hours
    # minimum doesn't apply
    loa_overlaps_month: bool = False


class WorkformSummary(BaseModel):
    month: str
    status: Literal["not_started", "draft", "submitted", "locked"]
    is_open: bool
    is_late: bool
    total_hours: float
    results: Dict[str, DepartmentResult] = Field(default_factory=dict)
    loa_overlaps_month: bool = False


class MyWorkformsResponse(BaseModel):
    open_months: List[str]
    workforms: List[WorkformSummary]


class PreferencesRequest(BaseModel):
    reminder_emails_enabled: bool
    review_emails_enabled: bool


class PreferencesResponse(PreferencesRequest):
    is_department_head: bool


class ReviewEntry(BaseModel):
    hours: float
    description: str
    work_date: Optional[date] = None
    loa_flag: Optional[str] = None


class ReviewItem(BaseModel):
    airtable_record_id: str
    staff_id: Optional[int] = None
    staff_name: str
    hours: Optional[float] = None
    description: Optional[str] = None
    decision: Optional[Literal["Approved", "Denied"]] = None
    entries: List[ReviewEntry]
    edited_in_airtable: bool
    submitted_at: Optional[datetime] = None
    is_late: bool
    loa_start: Optional[date] = None
    loa_end: Optional[date] = None
    loa_overlaps_month: bool


class ReviewQueueResponse(BaseModel):
    month: str
    department: str
    items: List[ReviewItem]
    total: int
    reviewed: int
    remaining: int


class ReviewOverviewResponse(BaseModel):
    is_operations_head: bool
    # Departments the reviewer heads (plus, for Operations heads, those with no head)
    own_departments: List[str]
    # Operations heads only: every other department
    fallback_departments: List[str]
    default_month: str
    # The first department with submissions waiting in default_month
    default_department: str
    # Months with submissions, newest first
    months: List[str]


class PendingCountsResponse(BaseModel):
    month: str
    pending: Dict[str, int]


class DecisionRequest(BaseModel):
    decision: Optional[Literal["Approved", "Denied"]] = None
