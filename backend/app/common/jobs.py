"""Scheduled jobs shared by every sub-site, as listed in KALX Staff Admin."""

from sqlalchemy.orm import Session

from app.common.schemas.admin import JobRunResult
from app.common.services.job_registry import COMMON_AREA, AdminJob
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


ADMIN_JOBS = [
    AdminJob(
        id="airtable_user_sync",
        name="Sync users from Airtable",
        area=COMMON_AREA,
        run=_run_airtable_user_sync,
    ),
]
