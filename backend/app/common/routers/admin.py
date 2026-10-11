"""
App-wide admin API endpoints (KALX Staff Admin): scheduled jobs, the audit
log and staging user impersonation. Admins are promotions staff and
department heads (see `get_admin_staff`).
"""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import (
    ACTIVE_STATUS,
    _is_promotions_staff,
    get_admin_staff,
    require_authentication,
)
from app.common.schemas.admin import (
    AuditLogItem,
    ImpersonateRequest,
    JobRunResult,
    JobStatus,
    UserListItem,
)
from app.common.services.job_registry import get_job, registered_jobs
from app.config import settings
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.impersonation_session import ImpersonationSession
from app.models.job_log import JobLog
from app.models.staff import Staff
from app.models.staff_status import StaffStatus
from app.scheduler import scheduler

router = APIRouter(prefix="/api/admin", tags=["admin"])

_LA = ZoneInfo("America/Los_Angeles")


def _require_staging():
    if settings.environment != "staging":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available in the staging environment",
        )


@router.get("/users", response_model=list[UserListItem])
def list_all_users(
    admin: Staff = Depends(get_admin_staff),
    db: Session = Depends(get_db),
) -> list[UserListItem]:
    """List all active users, promotions staff first, for the impersonation UI."""
    _require_staging()

    active_staff = (
        db.query(Staff)
        .join(StaffStatus, Staff.id == StaffStatus.staff_id)
        .filter(StaffStatus.status == ACTIVE_STATUS)
        .order_by(Staff.name)
        .all()
    )
    promotions = [s for s in active_staff if _is_promotions_staff(s)]
    staff = [s for s in active_staff if not _is_promotions_staff(s)]
    return [
        UserListItem(email=s.email, name=s.name, role="promotions") for s in promotions
    ] + [UserListItem(email=s.email, name=s.name, role="staff") for s in staff]


@router.get("/job-statuses", response_model=list[JobStatus])
def get_job_statuses(
    admin: Staff = Depends(get_admin_staff),
    db: Session = Depends(get_db),
) -> list[JobStatus]:
    """Return last-run and next-scheduled times for every registered job."""
    statuses = []
    for job in registered_jobs():
        last_log = (
            db.query(JobLog)
            .filter(JobLog.job_id == job.id)
            .order_by(JobLog.ran_at.desc())
            .first()
        )
        last_run_at = (
            last_log.ran_at.replace(tzinfo=timezone.utc).isoformat() if last_log else None
        )

        next_run_at = None
        try:
            scheduled = scheduler.get_job(job.id)
            if scheduled and scheduled.next_run_time:
                next_run_at = scheduled.next_run_time.isoformat()
        except Exception:
            pass

        statuses.append(
            JobStatus(
                id=job.id,
                name=job.name,
                area=job.area,
                can_run=job.run is not None,
                last_run_at=last_run_at,
                next_run_at=next_run_at,
            )
        )
    return statuses


@router.post("/jobs/{job_id}/run", response_model=JobRunResult)
async def run_job(
    job_id: str,
    admin: Staff = Depends(get_admin_staff),
    db: Session = Depends(get_db),
) -> JobRunResult:
    """Run a registered job now."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    if job.run is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{job.name} can't be run by hand",
        )
    return await job.run(db)


@router.post("/impersonate")
def start_impersonation(
    request: ImpersonateRequest,
    admin: Staff = Depends(get_admin_staff),
    db: Session = Depends(get_db),
):
    """Begin impersonating another user (staging only)."""
    _require_staging()

    # Remove any existing impersonation session for this user
    db.query(ImpersonationSession).filter(
        ImpersonationSession.real_email == admin.email
    ).delete()

    session = ImpersonationSession(
        real_email=admin.email,
        impersonated_email=request.email,
        impersonate_dj_network=request.is_dj_network,
        impersonate_station_office_network=request.is_station_office_network,
    )
    db.add(session)
    db.commit()
    return {
        "status": "ok",
        "impersonating": request.email,
        "is_dj_network": request.is_dj_network,
        "is_station_office_network": request.is_station_office_network,
    }


@router.delete("/impersonate")
def end_impersonation(
    email: str = Depends(require_authentication),
    db: Session = Depends(get_db),
):
    """
    End impersonation and return to own identity (staging only).

    Anyone signed in may end their own impersonation, so it can always be
    ended, even by someone who has stopped being an admin.
    """
    _require_staging()
    db.query(ImpersonationSession).filter(
        ImpersonationSession.real_email == email
    ).delete()
    db.commit()
    return {"status": "ok"}


@router.get("/audit-log", response_model=list[AuditLogItem])
def get_audit_log(
    admin: Staff = Depends(get_admin_staff),
    db: Session = Depends(get_db),
    event_type: str | None = Query(None),
    actor_email: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: int | None = Query(None),
    since: date | None = Query(None),
    until: date | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[AuditLogItem]:
    """
    Query the audit log.

    Supports filtering by event_type, actor_email, entity_type/id, and date range.
    since/until are interpreted as Pacific-time calendar dates (inclusive on both ends).
    Returns entries newest-first.
    """
    query = db.query(AuditLog)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if actor_email:
        query = query.filter(AuditLog.actor_email == actor_email)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == entity_id)
    if since:
        since_utc = (
            datetime.combine(since, time.min, tzinfo=_LA)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        query = query.filter(AuditLog.occurred_at >= since_utc)
    if until:
        until_utc = (
            datetime.combine(until, time.max, tzinfo=_LA)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        query = query.filter(AuditLog.occurred_at <= until_utc)
    rows = query.order_by(AuditLog.occurred_at.desc()).offset(offset).limit(limit).all()
    return [
        AuditLogItem(
            id=r.id,
            occurred_at=r.occurred_at,
            event_type=r.event_type,
            actor_email=r.actor_email,
            actor_role=r.actor_role,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            details=r.details,
        )
        for r in rows
    ]
