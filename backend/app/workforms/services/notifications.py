"""KALX Workforms emails: reminders to submit, and the review email for heads."""

import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.common.areas import WORKFORMS_AREA
from app.auth import ACTIVE_STATUS, _staff_statuses
from app.common.services.notification_service import send_email
from app.config import settings
from app.models.job_log import JobLog
from app.models.staff import Staff
from app.models.workform_department import DepartmentHead
from app.models.workform_preferences import WorkformPreferences
from app.workforms.services import records
from app.workforms.services.months import (
    PACIFIC,
    deadline,
    first_of_month,
    format_month,
    last_day_of_month,
    previous_month,
    today_pacific,
)
from app.workforms.services.review_service import responsible_pending_count

logger = logging.getLogger(__name__)

# Days of the month (besides the last day) reminders go out for last month
REMINDER_DAY_FOR_LAST_MONTH = 3
REVIEW_EMAIL_DAY = 6


def get_preferences(db: Session, staff: Staff) -> Optional[WorkformPreferences]:
    return (
        db.query(WorkformPreferences)
        .filter(WorkformPreferences.staff_id == staff.id)
        .first()
    )


def reminder_emails_enabled(db: Session, staff: Staff) -> bool:
    prefs = get_preferences(db, staff)
    return prefs is None or prefs.reminder_emails_enabled


def review_emails_enabled(db: Session, staff: Staff) -> bool:
    prefs = get_preferences(db, staff)
    return prefs is None or prefs.review_emails_enabled


def _head_record_ids(db: Session) -> set[str]:
    return {h.staff_airtable_record_id for h in db.query(DepartmentHead)}


def _workforms_url(path: str = "") -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/workforms/{path}"


def reminder_month(today: date) -> Optional[date]:
    """
    The month a reminder goes out for today, if any: this month on its last
    day, and last month on the 3rd.
    """
    if today == last_day_of_month(today):
        return first_of_month(today)
    if today.day == REMINDER_DAY_FOR_LAST_MONTH:
        return previous_month(first_of_month(today))
    return None


async def send_reminders(
    db: Session, today: Optional[date] = None, trigger: str = "scheduled"
) -> int:
    """
    Remind Active staff who haven't submitted a workform for the month.

    Runs daily and only sends on reminder days. Skips department heads, who
    don't need to fill in workforms, anyone who has submitted (a 0-hour
    workform counts), and anyone who turned reminders off.

    :returns: The number of reminders sent
    """
    today = today or today_pacific()
    month = reminder_month(today)
    if month is None:
        return 0
    await records.refresh_month(db, month)

    heads = _head_record_ids(db)
    due = deadline(month).astimezone(PACIFIC)
    sent = 0
    for staff in db.query(Staff).order_by(Staff.id):
        if ACTIVE_STATUS not in _staff_statuses(staff):
            continue
        if staff.airtable_record_id in heads:
            continue
        if records.record_for(db, staff.airtable_record_id, month) is not None:
            continue
        if not reminder_emails_enabled(db, staff):
            continue
        month_name = f"{month:%B %Y}"
        body = "\n".join([
            f"Hi {staff.name},",
            "",
            (
                f"You haven't submitted your KALX workform for {month_name} yet. It's due"
                f" by the end of {due:%A, %B} {due.day}."
            ),
            "",
            (
                "If you didn't do any work this month, you can submit a workform with no"
                " hours."
            ),
            "",
            (
                "Fill it in and submit it here:"
                f" {_workforms_url(f'month/{format_month(month)}')}"
            ),
            "",
            f"To stop these reminders, change your settings: {_workforms_url('settings')}",
        ])
        send_email(
            to_email=staff.email,
            subject=f"Reminder: submit your KALX workform for {month_name}",
            body_text=body,
            db=db,
            area=WORKFORMS_AREA,
        )
        sent += 1
    db.add(JobLog(job_id="workform_reminders", trigger=trigger))
    db.commit()
    logger.info("Sent %d workform reminders for %s", sent, format_month(month))
    return sent


async def send_review_emails(
    db: Session, today: Optional[date] = None, trigger: str = "scheduled"
) -> int:
    """
    Tell each department head how many of last month's submissions await
    their decision. Runs daily and only sends on the 6th.

    :returns: The number of emails sent
    """
    today = today or today_pacific()
    if today.day != REVIEW_EMAIL_DAY:
        return 0
    month = previous_month(first_of_month(today))
    await records.refresh_month(db, month)

    heads = _head_record_ids(db)
    sent = 0
    for staff in (
        db.query(Staff).filter(Staff.airtable_record_id.in_(heads)).order_by(Staff.id)
    ):
        if ACTIVE_STATUS not in _staff_statuses(staff):
            continue
        if not review_emails_enabled(db, staff):
            continue
        count = responsible_pending_count(db, staff, month)
        if not count:
            continue
        month_name = f"{month:%B %Y}"
        noun = "submission" if count == 1 else "submissions"
        body = "\n".join([
            f"Hi {staff.name},",
            "",
            (
                f"{count} workform {noun} for {month_name} {'is' if count == 1 else 'are'}"
                " waiting for you to approve or deny."
            ),
            "",
            f"Review them here: {_workforms_url(f'review/{format_month(month)}')}",
            "",
            f"To stop these emails, change your settings: {_workforms_url('settings')}",
        ])
        send_email(
            to_email=staff.email,
            subject=f"{count} KALX workform {noun} to review for {month_name}",
            body_text=body,
            db=db,
            area=WORKFORMS_AREA,
        )
        sent += 1
    db.add(JobLog(job_id="workform_review_emails", trigger=trigger))
    db.commit()
    logger.info("Sent %d workform review emails for %s", sent, format_month(month))
    return sent
