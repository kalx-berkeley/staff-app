"""Create or delete a throwaway staff/promotions user, typically on staging.

Writes directly to the database, bypassing Airtable — so the account is NOT
removed by the next Airtable sync (sync_from_airtable only upserts records
present in Airtable; see app/services/user_service.py). Delete it yourself
with the `delete` subcommand when you're done testing.

Run from the backend/ directory with the virtualenv activated:

    python scripts/test_user.py create
    python scripts/test_user.py create --email jane@example.com --role staff
    python scripts/test_user.py delete --email jane@example.com

Re-running `create` for an existing email updates its name/phone/role in
place (including removing departments/statuses that don't belong to the
new --role), so it also works to change an existing test user's role.

Refuses to run unless ENVIRONMENT=staging (as set in backend/.env) so it
can't be pointed at production by accident. Pass --force to override.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import SessionLocal
from app.models.pass_model import Pass
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus

DEFAULT_EMAIL = "test.promoter@example.com"
DEFAULT_NAME = "Test Promoter"
DEFAULT_PHONE = "555-0100"

# role -> (departments, statuses), matching the rules in app/auth.py and
# determine_user_role() in app/routers/users.py
ROLE_DEPARTMENTS_STATUSES: dict[str, tuple[list[str], list[str]]] = {
    "promotions": (["Promotions"], ["Active"]),
    "staff": ([], ["Active"]),
    "dj": ([], []),
}


def _require_staging(force: bool) -> None:
    """Abort unless running against a staging database.

    :param force: Skip the check if True.
    :type force: bool
    """
    if settings.environment != "staging" and not force:
        sys.exit(
            f"Refusing to run: ENVIRONMENT={settings.environment!r}, not 'staging' "
            "(pass --force to override)"
        )


def create_user(db: Session, email: str, name: str, phone: str, role: str) -> Staff:
    """Create or update a staff row so its departments/statuses match `role`.

    :param db: Active database session.
    :type db: Session
    :param email: Login email — must match the X-Forwarded-User header used to test.
    :type email: str
    :param name: Display name.
    :type name: str
    :param phone: Phone number (required, non-null column).
    :type phone: str
    :param role: One of "promotions", "staff", "dj".
    :type role: str
    :returns: The created or updated staff row.
    :rtype: Staff
    """
    staff = db.query(Staff).filter(Staff.email == email).first()
    if not staff:
        staff = Staff(email=email, name=name, phone=phone)
        db.add(staff)
        db.flush()
    else:
        staff.name = name
        staff.phone = phone

    target_departments, target_statuses = ROLE_DEPARTMENTS_STATUSES[role]

    existing_departments = {d.department: d for d in staff.departments}
    for department in target_departments:
        if department not in existing_departments:
            db.add(StaffDepartment(staff_id=staff.id, department=department))
    for department, row in existing_departments.items():
        if department not in target_departments:
            db.delete(row)

    existing_statuses = {s.status: s for s in staff.statuses}
    for status in target_statuses:
        if status not in existing_statuses:
            db.add(StaffStatus(staff_id=staff.id, status=status))
    for status, row in existing_statuses.items():
        if status not in target_statuses:
            db.delete(row)

    db.commit()
    db.refresh(staff)
    return staff


def delete_user(db: Session, email: str, force: bool) -> bool:
    """Delete a staff row by email, refusing if it has claimed passes.

    Pass.staff_id has no delete cascade, so deleting a staff row with
    claimed passes would leave those passes pointing at a nonexistent
    staff_id. Pass force=True to delete anyway.

    :param db: Active database session.
    :type db: Session
    :param email: Email of the staff row to delete.
    :type email: str
    :param force: Delete even if the staff row has claimed passes.
    :type force: bool
    :returns: True if a row was deleted, False if none was found.
    :rtype: bool
    """
    staff = db.query(Staff).filter(Staff.email == email).first()
    if not staff:
        return False

    claimed = db.query(Pass).filter(Pass.staff_id == staff.id).count()
    if claimed and not force:
        sys.exit(
            f"{email} has {claimed} claimed pass(es); pass --force to delete anyway "
            "(those passes will keep a dangling staff_id)"
        )

    db.delete(staff)
    db.commit()
    return True


def main() -> None:
    """Parse arguments and create or delete a test staff row."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Skip the staging-environment check (and, for delete, the claimed-passes check)"
        ),
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    create_parser = subparsers.add_parser("create", help="Create or update a test user")
    create_parser.add_argument("--email", default=DEFAULT_EMAIL)
    create_parser.add_argument("--name", default=DEFAULT_NAME)
    create_parser.add_argument("--phone", default=DEFAULT_PHONE)
    create_parser.add_argument(
        "--role", choices=sorted(ROLE_DEPARTMENTS_STATUSES), default="promotions"
    )

    delete_parser = subparsers.add_parser("delete", help="Delete a test user")
    delete_parser.add_argument("--email", required=True)

    args = parser.parse_args()
    _require_staging(args.force)

    db = SessionLocal()
    try:
        if args.action == "create":
            staff = create_user(db, args.email, args.name, args.phone, args.role)
            print(
                f"id={staff.id} email={staff.email} role={args.role} "
                f"departments={[d.department for d in staff.departments]} "
                f"statuses={[s.status for s in staff.statuses]}"
            )
        else:
            deleted = delete_user(db, args.email, args.force)
            print(f"{'Deleted' if deleted else 'No such user:'} {args.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
