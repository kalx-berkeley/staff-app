"""Scheduled jobs shared by every sub-site, as listed in KALX Staff Admin."""

from sqlalchemy.orm import Session

from app.common.schemas.admin import JobRunResult
from app.common.areas import ANALYTICS_AREA, COMMON_AREA
from app.common.services.analytics_rollup import roll_up_old_events
from app.common.services.job_registry import AdminJob
from app.common.services.spinitron_personas import JOB_ID as PERSONA_SYNC_JOB_ID
from app.common.services.spinitron_personas import sync_personas
from app.common.services.user_service import UserService


async def _run_airtable_user_sync(db: Session) -> JobRunResult:
    result = await UserService.sync_from_airtable(db, trigger="manual")
    n_promo = len(result["promotions_upserted"])
    n_staff = len(result["staff_upserted"])
    n_deactivated = len(result["deactivated"])
    n_err = len(result["errors"])
    msg = f"Synced {n_promo} promotions, {n_staff} staff"
    if n_deactivated:
        msg += f", {n_deactivated} deactivated"
    if n_err:
        msg += f", {n_err} error(s)"
    return JobRunResult(success=True, message=msg)


async def _run_analytics_rollup(db: Session) -> JobRunResult:
    n = roll_up_old_events(db)
    return JobRunResult(success=True, message=f"Rolled up {n} analytics event(s)")


async def _run_persona_sync(db: Session) -> JobRunResult:
    result = await sync_personas(db, trigger="manual")
    if result is None:
        return JobRunResult(
            success=False, message="Spinitron not configured — set SPINITRON_API_KEY"
        )
    msg = (
        f"Stored {result['personas']} persona(s); looked up {result['looked_up']}"
        " staff persona(s)' last playlist"
    )
    if result["errors"]:
        msg += f", {result['errors']} lookup(s) failed"
    return JobRunResult(success=True, message=msg)


ADMIN_JOBS = [
    AdminJob(
        id="airtable_user_sync",
        name="Sync users from Airtable",
        area=COMMON_AREA,
        run=_run_airtable_user_sync,
    ),
    AdminJob(
        id="analytics_rollup",
        name="Roll up analytics events older than 13 months",
        area=ANALYTICS_AREA,
        run=_run_analytics_rollup,
    ),
    AdminJob(
        id=PERSONA_SYNC_JOB_ID,
        name="Sync Spinitron personas and last playlists",
        area=COMMON_AREA,
        run=_run_persona_sync,
    ),
]
