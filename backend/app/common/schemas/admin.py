"""Schemas for the app-wide admin tools (KALX Staff Admin)."""

from typing import Any

from pydantic import BaseModel

from app.common.schemas.types import UtcDatetime


class JobStatus(BaseModel):
    id: str
    name: str
    # Which part of the app the job belongs to, e.g. "Radio Pass Giveaway"
    area: str
    # Whether admins can run the job by hand
    can_run: bool
    last_run_at: str | None
    next_run_at: str | None


class JobRunResult(BaseModel):
    success: bool
    message: str


class ImpersonateRequest(BaseModel):
    email: str | None = None
    is_dj_network: bool = False
    is_station_office_network: bool = False


class UserListItem(BaseModel):
    email: str
    name: str
    role: str  # "promotions" or "staff"


class AuditLogItem(BaseModel):
    id: int
    occurred_at: UtcDatetime
    event_type: str
    actor_email: str | None
    actor_role: str | None
    entity_type: str | None
    entity_id: int | None
    details: Any | None
