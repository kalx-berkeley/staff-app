"""KALX Workforms' scheduled jobs, as listed in KALX Staff Admin."""

from sqlalchemy.orm import Session

from app.common.areas import WORKFORMS_AREA
from app.common.schemas.admin import JobRunResult
from app.common.services.job_registry import AdminJob
from app.config import settings
from app.workforms.services.records import refresh_all


async def _run_workform_records_refresh(db: Session) -> JobRunResult:
    if not settings.airtable_api_key or not settings.airtable_base_id:
        return JobRunResult(
            success=False,
            message="Airtable not configured — set AIRTABLE_API_KEY and AIRTABLE_BASE_ID",
        )
    count = await refresh_all(db, trigger="manual")
    return JobRunResult(success=True, message=f"Copied {count} workform record(s)")


ADMIN_JOBS = [
    AdminJob(
        id="workform_records_refresh",
        name="Refresh workforms from Airtable",
        area=WORKFORMS_AREA,
        run=_run_workform_records_refresh,
    ),
    # Not runnable by hand: a second run on a reminder day would email every
    # reminder again.
    AdminJob(
        id="workform_emails",
        name="Send workform reminder and review emails",
        area=WORKFORMS_AREA,
    ),
]
