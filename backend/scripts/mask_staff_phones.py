"""Temporarily overwrite every staff member's phone number with a fake placeholder.

Intended for recording a tutorial video against the staging database without
exposing real staff phone numbers on screen. The nightly Airtable sync (or a
manual run of it) will restore the real numbers afterward.

Run from the backend/ directory with the virtualenv activated and
DATABASE_URL pointed at staging:

    python scripts/mask_staff_phones.py           # dry run: shows what would change
    python scripts/mask_staff_phones.py --yes      # actually overwrites

After recording, restore real numbers immediately rather than waiting for the
2 AM PT cron job: use the "Sync users from Airtable" action on the admin Jobs
page, or:

    curl -X POST https://<staging-host>/api/admin/jobs/airtable_user_sync/run

DO NOT run this against production. There is no environment check baked into
this script — that's on you to verify via DATABASE_URL before running.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models.staff import Staff

FAKE_PHONE = "555-0199"  # NANP block reserved for fictional use; never a real number


def main() -> None:
    """Overwrite (or preview overwriting) every staff member's phone number."""
    dry_run = "--yes" not in sys.argv

    db = SessionLocal()
    try:
        staff = db.query(Staff).all()
        to_change = [s for s in staff if s.phone != FAKE_PHONE]

        if dry_run:
            print(
                f"[dry run] Would overwrite {len(to_change)} of {len(staff)} phone numbers "
                f"with {FAKE_PHONE!r}."
            )
            print("Re-run with --yes to apply.")
            return

        for s in to_change:
            s.phone = FAKE_PHONE
        db.commit()
        print(
            f"Overwrote {len(to_change)} of {len(staff)} phone numbers with {FAKE_PHONE!r}."
        )
        print(
            "Remember to trigger the Airtable sync job now to restore real numbers "
            "instead of waiting for the nightly run."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
