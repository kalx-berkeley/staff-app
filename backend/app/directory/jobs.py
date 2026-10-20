"""The Staff Directory's scheduled jobs, as listed in KALX Staff Admin."""

from sqlalchemy.orm import Session

from app.common.areas import DIRECTORY_AREA
from app.common.schemas.admin import JobRunResult
from app.common.services.job_registry import AdminJob
from app.directory.services.shift_sync import JOB_ID, sync_shift_playlists


async def _run_dj_shift_sync(db: Session) -> JobRunResult:
    count = await sync_shift_playlists(db, trigger="manual")
    if count is None:
        return JobRunResult(
            success=False, message="Spinitron not configured — set SPINITRON_API_KEY"
        )
    return JobRunResult(success=True, message=f"Stored {count} playlist(s)")


ADMIN_JOBS = [
    AdminJob(
        id=JOB_ID,
        name="Sync DJ shifts from Spinitron",
        area=DIRECTORY_AREA,
        run=_run_dj_shift_sync,
    ),
]
