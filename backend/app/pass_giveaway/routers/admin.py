"""
Pass giveaway admin API endpoints: auto-close and lottery schedules, and
staging test data. The app-wide admin tools are in common/routers/admin.py.
"""

import csv
import random
from pathlib import Path
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_site_or_promotions_admin
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.venue import Venue
from app.models.venue_owner import VenueOwner
from app.models.show import Show
from app.pass_giveaway.services.pass_service import PassService
from app.config import settings
from app.scheduler import scheduler, schedule_auto_close_job
from app.pass_giveaway.guest_redaction import GuestRedactingRoute
from app.common.schemas.admin import JobRunResult

router = APIRouter(
    prefix="/api/pass-giveaway/admin",
    tags=["pass-giveaway-admin"],
    route_class=GuestRedactingRoute,
)

TEST_DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


class SeedResult(BaseModel):
    venues_added: int
    venues_skipped: int
    shows_added: int
    shows_skipped: int
    errors: list[str]


class AutoCloseScheduleItem(BaseModel):
    show_id: int
    event_name: str
    venue_name: str
    planned_close_date: date
    planned_close_time: time
    show_status: str
    schedule_status: str  # "scheduled" | "past" | "executed"


class LotteryScheduleItem(BaseModel):
    show_id: int
    event_name: str
    venue_name: str
    lottery_deadline: datetime
    staff_entry_count: int
    dj_entry_count: int
    show_status: str
    schedule_status: str  # "scheduled" | "past" | "complete"


def _require_staging():
    if settings.environment != "staging":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available in the staging environment",
        )


@router.get("/seed-status")
def get_seed_status(
    _: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Return whether test seed data has already been loaded."""
    _require_staging()
    venues_path = TEST_DATA_DIR / "venues.csv"
    if not venues_path.exists():
        return {"seeded": False}
    with open(venues_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        first_row = next(reader, None)
    if not first_row:
        return {"seeded": False}
    first_venue_name = first_row.get("name", "").strip()
    if not first_venue_name:
        return {"seeded": False}
    exists = db.query(Venue).filter(Venue.name == first_venue_name).first() is not None
    return {"seeded": exists}


@router.post("/seed-test-data", response_model=SeedResult)
def seed_test_data(
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
) -> SeedResult:
    """
    Seed the database with test venues and shows from CSV files.

    Only available in the staging environment. Additive — existing records are skipped.
    Venue owners are randomly assigned from existing promotions department members.
    Requires at least one Airtable sync to have populated promotions staff.
    Shows are created in published status.
    """
    _require_staging()

    errors: list[str] = []
    venues_added = 0
    venues_skipped = 0
    shows_added = 0
    shows_skipped = 0

    # Require promotions staff to exist (i.e. Airtable sync has run).
    promotions_staff = (
        db.query(Staff)
        .join(StaffDepartment, Staff.id == StaffDepartment.staff_id)
        .filter(StaffDepartment.department == "Promotions")
        .all()
    )
    if not promotions_staff:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "No promotions staff found. Run the Airtable sync before loading test data."
            ),
        )

    # --- Venues ---
    # Pre-process CSV: deduplicate by venue name (ignore any owner column).
    venue_rows: dict[str, str] = {}  # name → address
    venues_path = TEST_DATA_DIR / "venues.csv"
    if not venues_path.exists():
        errors.append(f"venues.csv not found at {venues_path}")
    else:
        with open(venues_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row.get("name", "").strip()
                address = row.get("address", "").strip()
                if not name:
                    continue
                if name not in venue_rows:
                    venue_rows[name] = address

        for name, address in venue_rows.items():
            existing = db.query(Venue).filter(Venue.name == name).first()
            if existing:
                venues_skipped += 1
                continue
            try:
                db.add(Venue(name=name, address=address))
                db.flush()
                new_venue = db.query(Venue).filter(Venue.name == name).first()
                owner_staff = random.choice(promotions_staff)
                db.add(VenueOwner(venue_id=new_venue.id, staff_id=owner_staff.id))
                db.commit()
                venues_added += 1
            except Exception as e:
                db.rollback()
                errors.append(f"Failed to add venue '{name}': {e}")

    # --- Shows ---
    shows_path = TEST_DATA_DIR / "shows.csv"
    if not shows_path.exists():
        errors.append(f"shows.csv not found at {shows_path}")
    else:
        with open(shows_path, newline="", encoding="utf-8") as f:
            show_rows = list(csv.DictReader(f))

        # Compute a date offset so the earliest show lands 7 days from today.
        valid_dates: list[date] = []
        for row in show_rows:
            try:
                valid_dates.append(date.fromisoformat(row.get("show_date", "").strip()))
            except ValueError:
                pass
        if valid_dates:
            earliest = min(valid_dates)
            target = date.today() + timedelta(days=7)
            date_offset = timedelta(days=(target - earliest).days)
        else:
            date_offset = timedelta(0)

        for row in show_rows:
            event_name = row.get("event_name", "").strip()
            if not event_name:
                continue

            show_date_str = row.get("show_date", "").strip()
            try:
                show_date = date.fromisoformat(show_date_str) + date_offset
            except ValueError:
                errors.append(f"Invalid show_date '{show_date_str}' for '{event_name}'")
                continue

            existing = (
                db.query(Show)
                .filter(Show.event_name == event_name, Show.show_date == show_date)
                .first()
            )
            if existing:
                shows_skipped += 1
                continue

            venue_name = row.get("venue_name", "").strip()
            venue = db.query(Venue).filter(Venue.name == venue_name).first()
            if not venue:
                errors.append(f"Venue '{venue_name}' not found for show '{event_name}'")
                continue

            show_time_str = row.get("show_time", "").strip()
            try:
                show_time = time.fromisoformat(show_time_str)
            except ValueError:
                errors.append(f"Invalid show_time '{show_time_str}' for '{event_name}'")
                continue

            age_restriction = row.get("age_restriction", "all_ages").strip()
            if age_restriction not in ("all_ages", "18+", "21+"):
                errors.append(
                    f"Invalid age_restriction '{age_restriction}' for '{event_name}'"
                )
                continue

            wheelchair_str = row.get("wheelchair_accessible", "yes").strip().lower()
            if wheelchair_str in ("true", "1", "yes"):
                wheelchair_accessible = "yes"
            elif wheelchair_str in ("false", "0", "no"):
                wheelchair_accessible = "no"
            else:
                wheelchair_accessible = "unknown"

            num_pass_pairs_str = row.get("num_pass_pairs", "1").strip()
            try:
                num_pass_pairs = int(num_pass_pairs_str)
                if not (1 <= num_pass_pairs <= 5):
                    raise ValueError
            except ValueError:
                errors.append(
                    f"Invalid num_pass_pairs '{num_pass_pairs_str}' for '{event_name}'"
                )
                continue

            caller_special_instructions = (
                row.get("special_instructions", "").strip() or None
            )
            genre_str = row.get("genre", "").strip()
            genre = [g.strip() for g in genre_str.split(",") if g.strip()] or None

            show_datetime = datetime.combine(show_date, show_time)
            close_datetime = show_datetime - timedelta(hours=24)
            planned_close_date = close_datetime.date()
            planned_close_time = close_datetime.time()

            try:
                show = Show(
                    event_name=event_name,
                    genre=genre,
                    venue_id=venue.id,
                    show_date=show_date,
                    show_time=show_time,
                    caller_special_instructions=caller_special_instructions,
                    age_restriction=age_restriction,
                    wheelchair_accessible=wheelchair_accessible,
                    num_pass_pairs=num_pass_pairs,
                    status="published",
                    auto_close=True,
                    planned_close_date=planned_close_date,
                    planned_close_time=planned_close_time,
                )
                db.add(show)
                db.commit()
                db.refresh(show)
                PassService.create_passes_for_show(db, show.id, show.num_pass_pairs)
                _LA = ZoneInfo("America/Los_Angeles")
                close_dt = datetime.combine(
                    planned_close_date, planned_close_time, tzinfo=_LA
                )
                if close_dt > datetime.now(_LA):
                    schedule_auto_close_job(show.id, close_dt)
                shows_added += 1
            except Exception as e:
                db.rollback()
                errors.append(f"Failed to add show '{event_name}': {e}")

    return SeedResult(
        venues_added=venues_added,
        venues_skipped=venues_skipped,
        shows_added=shows_added,
        shows_skipped=shows_skipped,
        errors=errors,
    )


@router.get("/auto-close-schedules", response_model=list[AutoCloseScheduleItem])
def get_auto_close_schedules(
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
) -> list[AutoCloseScheduleItem]:
    """List all shows with auto_close=True and their schedule status."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    _LA = ZoneInfo("America/Los_Angeles")
    now = datetime.now(_LA)

    shows = (
        db.query(Show)
        .filter(Show.auto_close.is_(True), Show.status != "deleted")
        .order_by(Show.planned_close_date, Show.planned_close_time)
        .all()
    )

    result = []
    for show in shows:
        if show.planned_close_date is None or show.planned_close_time is None:
            continue
        close_dt = datetime.combine(
            show.planned_close_date, show.planned_close_time, tzinfo=_LA
        )

        if show.status == "closed":
            sched_status = "executed"
        else:
            job_id = f"auto_close_show_{show.id}"
            try:
                job = scheduler.get_job(job_id)
                if job:
                    sched_status = "scheduled"
                elif close_dt > now:
                    # No job currently registered, but the close time hasn't
                    # passed — still pending, not "past".
                    sched_status = "scheduled"
                else:
                    sched_status = "past"
            except Exception:
                sched_status = "past" if close_dt <= now else "scheduled"

        result.append(
            AutoCloseScheduleItem(
                show_id=show.id,
                event_name=show.event_name,
                venue_name=show.venue.name,
                planned_close_date=show.planned_close_date,
                planned_close_time=show.planned_close_time,
                show_status=show.status,
                schedule_status=sched_status,
            )
        )
    return result


@router.get("/lottery-schedules", response_model=list[LotteryScheduleItem])
def get_lottery_schedules(
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
) -> list[LotteryScheduleItem]:
    """List all shows with lottery_enabled=True that are published and their schedule status."""
    from datetime import timedelta, timezone
    from app.models.lottery_entry import LotteryEntry

    shows = (
        db.query(Show)
        .filter(
            Show.lottery_enabled.is_(True),
            Show.published_at.isnot(None),
            Show.status.in_(["published", "closed"]),
        )
        .order_by(Show.published_at.desc())
        .all()
    )

    now = datetime.now(timezone.utc)
    result = []
    for show in shows:
        published = show.published_at
        if published is None:
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        deadline = published + timedelta(hours=show.lottery_window_hours)

        staff_count = (
            db.query(LotteryEntry)
            .filter(LotteryEntry.show_id == show.id, LotteryEntry.entry_type == "staff")
            .count()
        )
        dj_count = (
            db.query(LotteryEntry)
            .filter(LotteryEntry.show_id == show.id, LotteryEntry.entry_type == "dj")
            .count()
        )

        job_id = f"lottery_draw_{show.id}"
        try:
            job = scheduler.get_job(job_id)
            if job:
                sched_status = "scheduled"
            elif deadline > now:
                # No job currently registered, but the deadline hasn't passed —
                # still open, not "past". (Can happen transiently right after a
                # publish/reschedule before the job is registered.)
                sched_status = "scheduled"
            else:
                # Deadline passed — check if any pending entries remain
                has_pending = (
                    db.query(LotteryEntry)
                    .filter(
                        LotteryEntry.show_id == show.id,
                        LotteryEntry.status == "pending",
                    )
                    .first()
                ) is not None
                sched_status = "past" if has_pending else "complete"
        except Exception:
            sched_status = "past" if deadline <= now else "scheduled"

        result.append(
            LotteryScheduleItem(
                show_id=show.id,
                event_name=show.event_name,
                venue_name=show.venue.name,
                lottery_deadline=deadline,
                staff_entry_count=staff_count,
                dj_entry_count=dj_count,
                show_status=show.status,
                schedule_status=sched_status,
            )
        )
    return result


@router.post("/lottery-schedules/{show_id}/run", response_model=JobRunResult)
async def run_lottery_now(
    show_id: int,
    admin: Staff = Depends(get_site_or_promotions_admin),
    db: Session = Depends(get_db),
) -> JobRunResult:
    """Immediately execute the lottery draw for a show (site and promotions admins only)."""
    from app.pass_giveaway.services.lottery_service import LotteryService

    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Show not found")
    if not show.lottery_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lottery is not enabled for this show",
        )
    try:
        from app.scheduler import unschedule_lottery_job

        unschedule_lottery_job(show_id)
        result = LotteryService.run_lottery(db, show_id)
        staff = result.get("staff", {})
        dj = result.get("dj", {})
        return JobRunResult(
            success=True,
            message=(
                f"Lottery complete: {staff.get('winners', 0)} staff won, "
                f"{staff.get('losers', 0)} lost; "
                f"{dj.get('winners', 0)} DJ won, {dj.get('losers', 0)} lost."
            ),
        )
    except Exception as exc:
        return JobRunResult(success=False, message=str(exc))
