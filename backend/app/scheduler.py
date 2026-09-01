"""Scheduler for periodic tasks."""

import logging
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.services.user_service import UserService
from app.services.pass_service import PassService
from app.services.show_service import ShowService

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="America/Los_Angeles")


async def sync_users_from_airtable():
    """
    Scheduled task to sync users from Airtable.
    Runs daily at 2 AM.
    """
    from app.database import SessionLocal

    logger.info("Starting scheduled Airtable user sync")

    db = SessionLocal()
    try:
        result = await UserService.sync_from_airtable(db, trigger="scheduled")

        logger.info(
            "Scheduled sync completed successfully: "
            f"{len(result['promotions_upserted'])} promotions upserted, "
            f"{len(result['staff_upserted'])} staff upserted"
        )

        if result.get("errors"):
            logger.error(f"Sync completed with errors: {result['errors']}")

    except Exception as e:
        logger.error(f"Scheduled sync failed: {str(e)}", exc_info=True)
    finally:
        db.close()


async def expire_stale_dj_preassignments():
    """
    Scheduled task to clear DJ pre-assignments whose date has elapsed.
    Runs daily at 3 AM.
    """
    from app.database import SessionLocal

    logger.info("Starting scheduled expiry of stale DJ pre-assignments")

    db = SessionLocal()
    try:
        expired = PassService.expire_stale_preassignments(db, trigger="scheduled")
        logger.info(
            f"Stale preassignment expiry completed: {len(expired)} pass(es) cleared"
        )
    except Exception as e:
        logger.error(f"Stale preassignment expiry failed: {str(e)}", exc_info=True)
    finally:
        db.close()


async def notify_unclosed_past_shows():
    """
    Scheduled task to notify venue owners of published shows whose date has passed
    but have not been closed. Runs daily at 4 AM Pacific.
    """
    from app.database import SessionLocal

    logger.info("Starting scheduled notification for unclosed past shows")

    db = SessionLocal()
    try:
        count = ShowService.notify_unclosed_past_shows(db, trigger="scheduled")
        logger.info(
            f"Unclosed past show notification completed: {count} show(s) with notifications"
            " sent"
        )
    except Exception as e:
        logger.error(f"Unclosed past show notification failed: {str(e)}", exc_info=True)
    finally:
        db.close()


async def bootstrap_users_if_empty():
    """
    On startup, check if user tables are empty and sync from Airtable if so.
    This handles the case where a freshly deployed instance has no local user data.
    """
    if os.getenv("TESTING") == "1":
        return

    from app.database import SessionLocal
    from app.models.staff import Staff
    from app.models.staff_department import StaffDepartment

    db = SessionLocal()
    try:
        staff_count = db.query(Staff).count()
        promotions_count = (
            db.query(StaffDepartment)
            .filter(StaffDepartment.department == "Promotions")
            .count()
        )

        if promotions_count == 0 and staff_count == 0:
            logger.info("No user data found on startup - performing initial Airtable sync")
            await sync_users_from_airtable()
        else:
            logger.info(
                f"User data present on startup: {promotions_count} promotions, "
                f"{staff_count} staff - skipping bootstrap sync"
            )
    finally:
        db.close()


async def auto_close_show(show_id: int):
    """DateTrigger job that closes a show and emails venue owners the guest list."""
    from app.database import SessionLocal
    from app.models.show import Show
    from app.services.show_service import ShowService

    logger.info(f"Auto-closing show {show_id}")

    db = SessionLocal()
    try:
        show = db.query(Show).filter(Show.id == show_id).first()
        if show is None:
            logger.warning(f"Auto-close job: show {show_id} not found")
            return
        if show.status != "published":
            logger.info(
                f"Auto-close job: show {show_id} status is '{show.status}', skipping"
            )
            return
        ShowService.close_show(db, show_id)
        db.refresh(show)
        ShowService._notify_venue_owners_of_auto_close(db, show)
        from app.routers.shows import _notify_staff_guests_confirmed

        _notify_staff_guests_confirmed(db, show)
        logger.info(f"Auto-close complete for show {show_id} ({show.event_name})")
    except Exception as e:
        logger.error(f"Auto-close job failed for show {show_id}: {str(e)}", exc_info=True)
    finally:
        db.close()


def schedule_auto_close_job(show_id: int, run_date) -> None:
    """Add or replace an APScheduler DateTrigger job for a show's auto-close."""
    job_id = f"auto_close_show_{show_id}"
    scheduler.add_job(
        auto_close_show,
        trigger=DateTrigger(run_date=run_date),
        id=job_id,
        name=f"Auto-close show {show_id}",
        replace_existing=True,
        kwargs={"show_id": show_id},
    )
    logger.info(f"Scheduled auto-close job {job_id} at {run_date}")


def unschedule_auto_close_job(show_id: int) -> None:
    """Remove the auto-close APScheduler job for a show, if it exists."""
    job_id = f"auto_close_show_{show_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Removed auto-close job {job_id}")
    except Exception:
        pass


def _reschedule_pending_auto_close_jobs() -> None:
    """
    On startup, re-register DateTrigger auto-close jobs for shows that have
    auto_close=True, status='published', and a future planned close datetime.
    Shows whose window already passed are closed immediately.
    """
    if os.getenv("TESTING") == "1":
        return

    from app.database import SessionLocal
    from app.models.show import Show
    from app.services.show_service import ShowService
    from datetime import datetime
    from zoneinfo import ZoneInfo

    _LA = ZoneInfo("America/Los_Angeles")
    now = datetime.now(_LA)

    db = SessionLocal()
    try:
        pending = (
            db.query(Show)
            .filter(
                Show.auto_close.is_(True),
                Show.status == "published",
                Show.planned_close_date.isnot(None),
                Show.planned_close_time.isnot(None),
            )
            .all()
        )
        for show in pending:
            close_dt = datetime.combine(
                show.planned_close_date, show.planned_close_time, tzinfo=_LA
            )
            if close_dt > now:
                schedule_auto_close_job(show.id, close_dt)
            else:
                logger.warning(
                    f"Auto-close datetime for show {show.id} already passed "
                    f"({close_dt}); closing now"
                )
                try:
                    ShowService.close_show(db, show.id)
                    db.refresh(show)
                    ShowService._notify_venue_owners_of_auto_close(db, show)
                    from app.routers.shows import _notify_staff_guests_confirmed

                    _notify_staff_guests_confirmed(db, show)
                except Exception as e:
                    logger.error(f"Failed to close missed auto-close show {show.id}: {e}")
    finally:
        db.close()


async def run_lottery_draw(show_id: int):
    """DateTrigger job that runs the lottery for a show after its window closes."""
    from app.database import SessionLocal
    from app.models.show import Show
    from app.services.lottery_service import LotteryService

    logger.info(f"Running lottery draw for show {show_id}")

    db = SessionLocal()
    try:
        show = db.query(Show).filter(Show.id == show_id).first()
        if show is None:
            logger.warning(f"Lottery draw: show {show_id} not found")
            return
        if show.status != "published":
            logger.info(f"Lottery draw: show {show_id} status is '{show.status}', skipping")
            return
        result = LotteryService.run_lottery(db, show_id)
        logger.info(f"Lottery draw complete for show {show_id}: {result}")
    except Exception as e:
        logger.error(f"Lottery draw failed for show {show_id}: {str(e)}", exc_info=True)
    finally:
        db.close()


def schedule_lottery_job(show_id: int, run_date) -> None:
    """Add or replace an APScheduler DateTrigger job for a show's lottery draw."""
    job_id = f"lottery_draw_{show_id}"
    scheduler.add_job(
        run_lottery_draw,
        trigger=DateTrigger(run_date=run_date),
        id=job_id,
        name=f"Lottery draw show {show_id}",
        replace_existing=True,
        kwargs={"show_id": show_id},
    )
    logger.info(f"Scheduled lottery draw job {job_id} at {run_date}")


def unschedule_lottery_job(show_id: int) -> None:
    """Remove the lottery draw APScheduler job for a show, if it exists."""
    job_id = f"lottery_draw_{show_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Removed lottery draw job {job_id}")
    except Exception:
        pass


def _reschedule_pending_lottery_jobs() -> None:
    """
    On startup, re-register DateTrigger lottery jobs for published shows with an active
    lottery window. Shows whose window already passed have the lottery run immediately.
    """
    if os.getenv("TESTING") == "1":
        return

    from app.database import SessionLocal
    from app.models.show import Show
    from app.models.lottery_entry import LotteryEntry
    from app.services.lottery_service import LotteryService
    from datetime import timedelta, timezone

    db = SessionLocal()
    try:
        pending = (
            db.query(Show)
            .filter(
                Show.lottery_enabled.is_(True),
                Show.status == "published",
                Show.published_at.isnot(None),
            )
            .all()
        )
        for show in pending:
            has_pending_entries = (
                db.query(LotteryEntry)
                .filter(
                    LotteryEntry.show_id == show.id,
                    LotteryEntry.status == "pending",
                )
                .first()
                is not None
            )
            if not has_pending_entries:
                continue

            published = show.published_at
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            deadline = published + timedelta(hours=show.lottery_window_hours)
            now = datetime.now(timezone.utc)
            if deadline > now:
                schedule_lottery_job(show.id, deadline)
            else:
                logger.warning(
                    f"Lottery deadline for show {show.id} already passed ({deadline}); "
                    "running lottery now"
                )
                try:
                    LotteryService.run_lottery(db, show.id)
                except Exception as e:
                    logger.error(f"Failed to run missed lottery for show {show.id}: {e}")
    finally:
        db.close()


def start_scheduler():
    """
    Start the scheduler and add jobs.
    Skips starting if in test environment.
    """
    # Skip scheduler in test environment
    if os.getenv("TESTING") == "1":
        logger.info("Skipping scheduler startup in test environment")
        return

    _PT = "America/Los_Angeles"

    # Add daily sync job at 2 AM Pacific
    scheduler.add_job(
        sync_users_from_airtable,
        trigger=CronTrigger(hour=2, minute=0, timezone=_PT),
        id="airtable_user_sync",
        name="Sync users from Airtable",
        replace_existing=True,
    )

    # Add daily job at 3 AM Pacific to clear elapsed DJ pre-assignments
    scheduler.add_job(
        expire_stale_dj_preassignments,
        trigger=CronTrigger(hour=3, minute=0, timezone=_PT),
        id="expire_stale_dj_preassignments",
        name="Expire stale DJ pre-assignments",
        replace_existing=True,
    )

    # Add daily job at 4 AM Pacific to notify venue owners of unclosed past shows
    scheduler.add_job(
        notify_unclosed_past_shows,
        trigger=CronTrigger(hour=4, minute=0, timezone=_PT),
        id="notify_unclosed_past_shows",
        name="Notify venue owners of unclosed past shows",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started - Airtable sync at 2 AM PT, stale preassignment expiry at 3 AM"
        " PT, unclosed past show notifications at 4 AM PT"
    )
    _reschedule_pending_auto_close_jobs()
    _reschedule_pending_lottery_jobs()


def shutdown_scheduler():
    """
    Shutdown the scheduler gracefully.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down")
