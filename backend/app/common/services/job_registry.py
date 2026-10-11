"""
The scheduled jobs listed in KALX Staff Admin.

Each sub-site describes its own jobs, and `main.py` registers them here, so
the common admin tools can list and run every job without importing a
sub-site.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.common.schemas.admin import JobRunResult

COMMON_AREA = "Common"


@dataclass(frozen=True)
class AdminJob:
    """A scheduled job, as shown in KALX Staff Admin."""

    # The APScheduler job ID, which is also the JobLog job_id of its runs
    id: str
    name: str
    # Which part of the app the job belongs to, e.g. "Radio Pass Giveaway"
    area: str
    # Runs the job now. None for jobs that are unsafe to run by hand.
    run: Optional[Callable[[Session], Awaitable[JobRunResult]]] = None


_jobs: Dict[str, AdminJob] = {}


def register_job(job: AdminJob) -> None:
    """List *job* in KALX Staff Admin."""
    _jobs[job.id] = job


def registered_jobs() -> List[AdminJob]:
    """Every registered job, in the order registered."""
    return list(_jobs.values())


def get_job(job_id: str) -> Optional[AdminJob]:
    return _jobs.get(job_id)
