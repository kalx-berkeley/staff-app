"""The pass giveaway's scheduled jobs, as listed in KALX Staff Admin."""

from sqlalchemy.orm import Session

from app.common.schemas.admin import JobRunResult
from app.common.services.job_registry import AdminJob
from app.config import settings
from app.pass_giveaway.services.feature_bin_service import FeatureBinService
from app.pass_giveaway.services.kalx_live_service import KalxLiveService
from app.pass_giveaway.services.pass_service import PassService
from app.pass_giveaway.services.show_service import ShowService
from app.pass_giveaway.services.spinitron_schedule_service import (
    SpinitronScheduleService,
)

AREA = "Radio Pass Giveaway"


async def _run_feature_bin_sync(db: Session) -> JobRunResult:
    if not FeatureBinService.is_configured():
        return JobRunResult(
            success=False,
            message=(
                "Feature bin sheet not configured — set FEATURE_BIN_SHEET_ID and"
                " FEATURE_BIN_SHEET_GID"
            ),
        )
    count = FeatureBinService.sync_feature_bin(db, trigger="manual")
    return JobRunResult(success=True, message=f"Synced {count} feature bin release(s)")


async def _run_kalx_live_sync(db: Session) -> JobRunResult:
    if not KalxLiveService.is_configured():
        return JobRunResult(
            success=False,
            message="KALX Live calendar not configured — set KALX_LIVE_CALENDAR_ID",
        )
    count = KalxLiveService.sync_kalx_live(db, trigger="manual")
    return JobRunResult(success=True, message=f"Synced {count} KALX Live appearance(s)")


async def _run_expire_stale_dj_preassignments(db: Session) -> JobRunResult:
    expired = PassService.expire_stale_preassignments(db, trigger="manual")
    return JobRunResult(success=True, message=f"Expired {len(expired)} pre-assignment(s)")


async def _run_notify_unclosed_past_shows(db: Session) -> JobRunResult:
    count = ShowService.notify_unclosed_past_shows(db, trigger="manual")
    return JobRunResult(
        success=True,
        message=f"Notified venue owners for {count} unclosed past show(s)",
    )


async def _run_spinitron_schedule_sync(db: Session) -> JobRunResult:
    if not settings.spinitron_api_key:
        return JobRunResult(
            success=False,
            message="Spinitron not configured — set SPINITRON_API_KEY",
        )
    count = await SpinitronScheduleService.sync_schedule(db, trigger="manual")
    return JobRunResult(
        success=True, message=f"Cached {count} Spinitron show(s)/playlist(s)"
    )


ADMIN_JOBS = [
    AdminJob(
        id="feature_bin_sync",
        name="Sync feature bin from Google Sheet",
        area=AREA,
        run=_run_feature_bin_sync,
    ),
    AdminJob(
        id="kalx_live_sync",
        name="Sync KALX Live calendar",
        area=AREA,
        run=_run_kalx_live_sync,
    ),
    AdminJob(
        id="expire_stale_dj_preassignments",
        name="Expire stale DJ pre-assignments",
        area=AREA,
        run=_run_expire_stale_dj_preassignments,
    ),
    AdminJob(
        id="notify_unclosed_past_shows",
        name="Notify venue owners of unclosed past shows",
        area=AREA,
        run=_run_notify_unclosed_past_shows,
    ),
    AdminJob(
        id="spinitron_schedule_sync",
        name="Sync Spinitron on-air schedule",
        area=AREA,
        run=_run_spinitron_schedule_sync,
    ),
]
