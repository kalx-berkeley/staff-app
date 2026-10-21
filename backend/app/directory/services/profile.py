"""The Staff Directory's profile page: what it shows, and saving edits to Airtable."""

import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.common.areas import DIRECTORY_AREA
from app.common.services import profile_providers, staff_airtable
from app.common.services.audit_service import log_event
from app.common.services.leave_service import on_leave, today_pt
from app.common.services.spinitron_service import (
    cached_persona_names,
    placeholder_persona_ids,
)
from app.common.services.user_service import UserService
from app.config import settings
from app.directory.schemas.directory import (
    Check,
    DepartmentCheckResponse,
    EligibilityResponse,
    LeaveCheck,
    MonthCheckResponse,
    PlaylistCheckResponse,
    ProfileUpdate,
    QuizCheckResponse,
    ShiftCheck,
    WorkformMonth,
    WorkformsCheck,
)
from app.directory.services import eligibility as rules
from app.directory.services.shift_sync import last_synced_at, window_start
from app.models.dj_quiz_deadline import DjQuizDeadline
from app.models.dj_shift_playlist import DjShiftPlaylist
from app.models.staff import Staff

WORKFORM_SUMMARY_MONTHS = 12

_PERSONA_URL_RE = re.compile(
    r"^https?://(?:widgets\.)?spinitron\.com/KALX/dj/(\d+)(?:[/?#]|$)"
)
_ALLOWED_PHOTO_TYPES = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024


def _statuses(staff: Staff) -> List[str]:
    return [s.status for s in staff.statuses]


def shows_eligibility(staff: Staff) -> bool:
    """Whether the profile shows the Sublist DJ requirements: the person has a
    Spinitron persona or the Sublist DJ status."""
    return bool(staff.spinitron_ids) or rules.SUBLIST_DJ_STATUS in _statuses(staff)


def _month_key(month: date) -> str:
    return month.strftime("%Y-%m")


def _quiz_deadlines(db: Session) -> Dict[int, date]:
    return {row.year: row.deadline for row in db.query(DjQuizDeadline)}


# --- Eligibility -----------------------------------------------------------


def _sublist_check(staff: Staff) -> Check:
    if rules.SUBLIST_DJ_STATUS in _statuses(staff):
        return Check(met=True, summary="On the DJ sublist")
    return Check(met=False, summary="Not on the DJ sublist")


def _leave_check(staff: Staff, today: date) -> LeaveCheck:
    has_status = any(s.casefold() == rules.ON_LEAVE_STATUS for s in _statuses(staff))
    if on_leave(staff, today):
        summary = (
            f"On leave until {rules.format_day(staff.loa_end)}"
            if staff.loa_end
            else "On leave of absence"
        )
        met = False
    elif has_status:
        summary, met = "Airtable has an On leave status for you", False
    else:
        summary, met = "Not on leave", True
    return LeaveCheck(
        met=met, summary=summary, loa_start=staff.loa_start, loa_end=staff.loa_end
    )


def _shift_check(
    db: Session, staff: Staff, today: date
) -> Tuple[ShiftCheck, List[rules.Shift]]:
    current = rules.quarter_start(today)
    previous = rules.add_months(current, -3)
    base = dict(
        previous_quarter=rules.quarter_label(previous),
        current_quarter=rules.quarter_label(current),
        min_minutes=rules.MIN_SHIFT_MINUTES,
    )
    synced_at = last_synced_at(db)
    if synced_at is None:
        return (
            ShiftCheck(
                met=None, summary="DJ shifts haven't been copied from Spinitron yet", **base
            ),
            [],
        )
    persona_ids = staff.spinitron_ids or []
    rows = (
        db.query(DjShiftPlaylist)
        .filter(
            DjShiftPlaylist.persona_id.in_(persona_ids),
            DjShiftPlaylist.start >= window_start(today),
        )
        .all()
        if persona_ids
        else []
    )
    playlists = rules.own_playlists(
        (
            rules.Playlist(
                id=r.id,
                persona_id=r.persona_id,
                show_id=r.show_id,
                start=r.start,
                end=r.end,
                title=r.title,
                automation=r.automation,
            )
            for r in rows
        ),
        persona_ids,
        placeholder_persona_ids(),
    )
    specialty_ids = profile_providers.specialty_show_ids(db) or set()
    shifts, checks = rules.find_shifts(playlists, specialty_ids)
    qualifying = [s for s in shifts if s.qualifies and s.quarter == previous]
    if qualifying:
        last = qualifying[-1]
        parts = [rules.format_day(last.start.astimezone(rules.PACIFIC).date())]
        if last.title:
            parts.append(last.title)
        parts.append(rules.format_minutes(last.minutes))
        summary = "Last qualifying shift: " + ", ".join(parts)
    else:
        summary = f"No qualifying shift in {rules.quarter_label(previous)}"
    playlist_checks = []
    for check in checks:
        p = check.playlist
        quarter = rules.quarter_start(p.start.astimezone(rules.PACIFIC).date())
        playlist_checks.append(
            PlaylistCheckResponse(
                id=p.id,
                start=p.start,
                end=p.end,
                title=p.title,
                minutes=int((p.end - p.start).total_seconds() // 60),
                shift_minutes=check.shift_minutes,
                counted=check.counted,
                reason=check.reason,
                quarter="current" if quarter == current else "previous",
                url=f"https://spinitron.com/KALX/pl/{p.id}/",
            )
        )
    return (
        ShiftCheck(
            met=bool(qualifying),
            summary=summary,
            playlists=playlist_checks,
            shifts_as_of=synced_at,
            **base,
        ),
        shifts,
    )


def _workforms_check(db: Session, staff: Staff, today: date) -> WorkformsCheck:
    months = rules.workform_months(today)
    hours = profile_providers.monthly_hours(db, staff, months)
    if hours is None:
        return WorkformsCheck(
            met=None,
            summary="Workforms aren't available",
            required_hours=rules.REQUIRED_MONTHLY_HOURS,
        )
    checks = [rules.check_month(hours[m], most_recent=i == 0) for i, m in enumerate(months)]
    return WorkformsCheck(
        met=all(c.met for c in checks),
        # Oldest first reads naturally: "Jul 6 h ✓, Aug 4.5 h ✗, Sep 7 h ✓"
        summary=", ".join(rules.month_summary(c) for c in reversed(checks)),
        required_hours=rules.REQUIRED_MONTHLY_HOURS,
        months=[
            MonthCheckResponse(
                month=_month_key(c.month),
                most_recent=c.most_recent,
                met=c.met,
                counted_hours=c.counted_hours,
                status=c.status,
                loa=c.loa,
                departments=[
                    DepartmentCheckResponse(
                        department=d.department,
                        hours=d.hours,
                        decision=d.decision,
                        counted=d.counted,
                    )
                    for d in c.departments
                ],
                pending_departments=c.pending_departments,
            )
            for c in checks
        ],
    )


def _quiz_check(
    db: Session, staff: Staff, today: date
) -> Tuple[QuizCheckResponse, rules.QuizCheck]:
    quiz = rules.check_quiz(staff.dj_quiz_years or [], _quiz_deadlines(db), today)
    if quiz.due is not None:
        summary = f"{today.year} quiz due {rules.format_day(quiz.due)}"
        if not quiz.met:
            summary = f"{quiz.current_year} quiz not done; " + summary
    elif quiz.met:
        summary = f"{max(quiz.years)} quiz done"
    else:
        summary = f"{quiz.current_year} quiz not done"
    return (
        QuizCheckResponse(
            met=quiz.met,
            summary=summary,
            current_year=quiz.current_year,
            years=quiz.years,
            this_year_deadline=quiz.this_year_deadline,
            due=quiz.due,
            deadline_announced=quiz.deadline_announced,
        ),
        quiz,
    )


def build_eligibility(
    db: Session, staff: Staff, today: Optional[date] = None
) -> EligibilityResponse:
    """The Sublist DJ requirements for *staff*, as of *today* (Pacific)."""
    today = today or today_pt()
    sublist = _sublist_check(staff)
    leave = _leave_check(staff, today)
    shift, shifts = _shift_check(db, staff, today)
    workforms = _workforms_check(db, staff, today)
    quiz, quiz_rule = _quiz_check(db, staff, today)
    checks = [sublist, leave, shift, workforms, quiz]
    eligible = all(c.met for c in checks)
    return EligibilityResponse(
        eligible=eligible,
        unmet=sum(1 for c in checks if c.met is False),
        unavailable=sum(1 for c in checks if c.met is None),
        eligible_until=(
            rules.eligible_until(today, shifts, quiz_rule, staff.loa_start)
            if eligible
            else None
        ),
        next_workform_note=rules.next_workform_note(today),
        sublist=sublist,
        leave=leave,
        shift=shift,
        workforms=workforms,
        quiz=quiz,
    )


# --- Workforms summary -----------------------------------------------------


def build_workforms_summary(
    db: Session, staff: Staff, today: Optional[date] = None
) -> Optional[List[WorkformMonth]]:
    """This month and the 11 before it, most recent first, or None when
    workforms aren't available."""
    today = today or today_pt()
    this_month = date(today.year, today.month, 1)
    months = [rules.add_months(this_month, -n) for n in range(WORKFORM_SUMMARY_MONTHS)]
    hours = profile_providers.monthly_hours(db, staff, months)
    if hours is None:
        return None
    return [
        WorkformMonth(
            month=_month_key(m),
            status=hours[m].status,
            reported_hours=hours[m].reported_hours,
            approved_hours=sum(
                d.hours for d in hours[m].departments if d.decision == "Approved"
            ),
            is_late=hours[m].is_late,
            loa=hours[m].loa_overlaps_month,
        )
        for m in months
    ]


# --- Editing ---------------------------------------------------------------


def require_editing_enabled() -> None:
    if not settings.directory_self_edit_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editing isn't available yet",
        )


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    A US phone number as "(510) 642-1111", or None when blank.

    :raises HTTPException: 422 if it isn't a 10-digit US number.
    """
    if phone is None or not phone.strip():
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Phone must be a 10-digit US number",
        )
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip() or None


def dj_name_markdown(personas: List[Tuple[int, str]]) -> str:
    """The Airtable "DJ Name" value for these personas: Markdown links joined by ", "."""
    links = []
    for persona_id, name in personas:
        label = name.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
        links.append(f"[{label}](https://spinitron.com/KALX/dj/{persona_id}/)")
    return ", ".join(links)


async def persona_names(db: Session) -> Dict[int, str]:
    """Every Spinitron persona except the placeholders, by ID."""
    placeholders = placeholder_persona_ids()
    try:
        names = await cached_persona_names(db)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Couldn't load DJ names from Spinitron: {e}",
        )
    return {pid: name for pid, name in names.items() if pid not in placeholders}


async def resolve_persona_url(db: Session, url: str) -> Tuple[int, str]:
    """
    The persona a pasted Spinitron DJ link points to.

    :raises HTTPException: 400 if it isn't a DJ link, or is a placeholder or
        unknown persona.
    """
    match = _PERSONA_URL_RE.match(url.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "That isn't a Spinitron DJ link, like https://spinitron.com/KALX/dj/123456/"
            ),
        )
    persona_id = int(match.group(1))
    if persona_id in placeholder_persona_ids():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That's a shared Spinitron identity, not a DJ name",
        )
    names = await persona_names(db)
    if persona_id not in names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spinitron has no DJ with that link",
        )
    return persona_id, names[persona_id]


async def update_profile(
    db: Session, staff: Staff, update: ProfileUpdate, actor_email: str
) -> None:
    """
    Write a profile's changed fields to Airtable, re-sync the staff member,
    and log the change.

    :raises HTTPException: 422 for invalid values, 400 for an unknown or
        placeholder persona, 409 if the staff member has no Airtable record,
        and 502/503 if Airtable fails.
    """
    first_name = (update.first_name or "").strip()
    if not first_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="First name is required",
        )
    new_values: Dict[str, Any] = {
        "first_name": first_name,
        "surname": _blank_to_none(update.surname),
        "pronouns": _blank_to_none(update.pronouns),
        "phone": normalize_phone(update.phone),
    }
    persona_ids: List[int] = []
    for pid in update.dj_persona_ids:
        if pid not in persona_ids:
            persona_ids.append(pid)
    current_ids = staff.spinitron_ids or []
    personas_changed = persona_ids != current_ids
    names: Dict[int, str] = {}
    if personas_changed:
        names = await persona_names(db)
        unknown = [pid for pid in persona_ids if pid not in names]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="These aren't DJ names in Spinitron: "
                + ", ".join(str(pid) for pid in unknown),
            )

    current_values = {
        "first_name": staff.first_name,
        "surname": staff.surname,
        "pronouns": staff.pronouns,
        "phone": staff.phone or None,
    }
    airtable_fields = {
        "first_name": "First Name",
        "surname": "Surname",
        "pronouns": "Pronouns",
        "phone": "Phone",
    }
    changes: Dict[str, Dict[str, Any]] = {}
    fields: Dict[str, Any] = {}
    for key, value in new_values.items():
        if value != current_values[key]:
            changes[key] = {"before": current_values[key], "after": value}
            fields[airtable_fields[key]] = value
    if personas_changed:
        changes["dj_persona_ids"] = {"before": current_ids, "after": persona_ids}
        fields["DJ Name"] = (
            dj_name_markdown([(pid, names[pid]) for pid in persona_ids]) or None
        )
    if not fields:
        return
    if not staff.airtable_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This staff member has no Airtable record to update",
        )
    await staff_airtable.update_staff_record(staff.airtable_record_id, fields)
    await UserService.sync_one(db, staff.airtable_record_id)
    log_event(
        db,
        event_type="profile_updated",
        area=DIRECTORY_AREA,
        actor_email=actor_email,
        actor_role="staff" if actor_email == staff.email else "paid_staff",
        entity_type="staff",
        entity_id=staff.id,
        details={"email": staff.email, "changes": changes},
    )


def check_photo(content_type: Optional[str], data: bytes) -> str:
    """
    The photo's content type, if it's a JPEG or PNG within the size limit.

    :raises HTTPException: 413 if it's too big, 422 if it isn't a JPEG or PNG.
    """
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The photo must be 5 MB or smaller",
        )
    signature = _ALLOWED_PHOTO_TYPES.get(content_type or "")
    if signature is None or not data.startswith(signature):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The photo must be a JPEG or PNG",
        )
    return content_type


async def replace_photo(
    db: Session,
    staff: Staff,
    filename: str,
    content_type: Optional[str],
    data: bytes,
    actor_email: str,
) -> None:
    """Upload a new photo to Airtable in place of the old one, and re-sync."""
    content_type = check_photo(content_type, data)
    if not staff.airtable_record_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This staff member has no Airtable record to update",
        )
    await staff_airtable.replace_staff_photo(
        staff.airtable_record_id, filename or "photo", content_type, data
    )
    await UserService.sync_one(db, staff.airtable_record_id)
    log_event(
        db,
        event_type="profile_photo_updated",
        area=DIRECTORY_AREA,
        actor_email=actor_email,
        actor_role="staff" if actor_email == staff.email else "paid_staff",
        entity_type="staff",
        entity_id=staff.id,
        details={"email": staff.email},
    )
