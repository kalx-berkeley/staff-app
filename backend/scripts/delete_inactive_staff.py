"""Delete staff rows that aren't "Active" and that nothing else refers to.

The Airtable sync once imported every record in the staff table, including
people who aren't active yet ("🆕"); it now imports only "Active" records
(see app/services/user_service.py), but the rows it already created stay.
This removes them, along with any other leftover staff row without "Active"
status (e.g. former staff the sync deactivated) that no pass, lottery entry,
alternate, or venue/promoter/specialty-show ownership refers to.

A deleted row's own data goes with it: departments, statuses, notification
and genre preferences, and directory photos. Audit log events are kept. Any
other table with a foreign key to staff.id counts as a reference, so rows
still tied to history are left alone.

Run from the backend/ directory with the virtualenv activated and
DATABASE_URL pointed at the target database:

    python scripts/delete_inactive_staff.py           # dry run: lists the rows
    python scripts/delete_inactive_staff.py --apply   # actually deletes them

Run it after deploying the sync change, or the next sync re-creates the rows.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: E402,F401  (registers every table on Base.metadata)
from app.auth import ACTIVE_STATUS  # noqa: E402
from app.database import Base, SessionLocal  # noqa: E402
from app.models.staff import Staff  # noqa: E402
from app.models.staff_status import StaffStatus  # noqa: E402
from app.services.staff_photo_service import delete_photo  # noqa: E402

# Tables holding a staff member's own data, deleted along with the row.
OWNED_TABLES = {
    "staff_departments",
    "staff_statuses",
    "notification_preferences",
    "staff_genre_preferences",
}


def _staff_foreign_keys() -> list[tuple[str, object]]:
    """
    Return every (table name, column) that has a foreign key to staff.id.

    :returns: List of (table name, Column) pairs, excluding the staff table.
    """
    staff_id = Staff.__table__.c.id
    return [
        (table.name, column)
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if any(fk.column is staff_id for fk in column.foreign_keys)
    ]


def main() -> None:
    """List (or delete) unreferenced staff rows without "Active" status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply", action="store_true", help="delete the rows instead of listing them"
    )
    args = parser.parse_args()

    foreign_keys = _staff_foreign_keys()
    owned = [(name, col) for name, col in foreign_keys if name in OWNED_TABLES]
    references = [(name, col) for name, col in foreign_keys if name not in OWNED_TABLES]

    db = SessionLocal()
    try:
        active_ids = select(StaffStatus.staff_id).where(StaffStatus.status == ACTIVE_STATUS)
        query = db.query(Staff).filter(Staff.id.not_in(active_ids))
        for _, column in references:
            query = query.filter(Staff.id.not_in(select(column).where(column.is_not(None))))
        to_delete = query.order_by(Staff.email).all()

        for staff in to_delete:
            statuses = ", ".join(sorted(s.status for s in staff.statuses)) or "none"
            print(f"{staff.id}\t{staff.email}\t{staff.name}\tstatuses: {statuses}")

        if not args.apply:
            print(f"[dry run] Would delete {len(to_delete)} staff rows.")
            print("Re-run with --apply to delete them.")
            return

        ids = [staff.id for staff in to_delete]
        for _, column in owned:
            db.execute(delete(column.table).where(column.in_(ids)))
        db.execute(delete(Staff.__table__).where(Staff.id.in_(ids)))
        db.commit()
        for staff_id in ids:
            delete_photo(staff_id)
        print(f"Deleted {len(ids)} staff rows.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
