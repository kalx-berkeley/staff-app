"""Seed a local development database with promotions staff and a test venue.

Run from the backend/ directory with the virtualenv activated:

    python scripts/seed_local_dev.py

Safe to re-run: existing staff/venue rows with matching email/name are left untouched.
"""

import sys
from pathlib import Path

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.venue import Venue
from app.models.venue_owner import VenueOwner

PROMOTIONS_STAFF = [
    ("test@example.com", "Test Promoter"),
    ("jane.smith@example.com", "Jane Smith"),
    ("john.doe@example.com", "John Doe"),
]

TEST_VENUE_NAME = "Test Venue"
TEST_VENUE_ADDRESS = "123 Test St"


def _get_or_create_staff(db: Session, email: str, name: str) -> Staff:
    """Return an existing Promotions-department staff member, or create one.

    :param db: Active database session.
    :type db: Session
    :param email: Staff member's email address.
    :type email: str
    :param name: Staff member's display name.
    :type name: str
    :returns: The staff member, with Active status and Promotions department.
    :rtype: Staff
    """
    existing = db.query(Staff).filter(Staff.email == email).first()
    if existing:
        return existing
    staff = Staff(email=email, name=name, phone="555-0100")
    db.add(staff)
    db.flush()
    db.add(StaffDepartment(staff_id=staff.id, department="Promotions"))
    db.add(StaffStatus(staff_id=staff.id, status="Active"))
    return staff


def _get_or_create_test_venue(db: Session, owner: Staff) -> Venue:
    """Return the existing test venue, or create one owned by `owner`.

    :param db: Active database session.
    :type db: Session
    :param owner: Staff member to record as the venue's owner.
    :type owner: Staff
    :returns: The test venue.
    :rtype: Venue
    """
    existing = db.query(Venue).filter(Venue.name == TEST_VENUE_NAME).first()
    if existing:
        return existing
    venue = Venue(name=TEST_VENUE_NAME, address=TEST_VENUE_ADDRESS)
    db.add(venue)
    db.flush()
    db.add(VenueOwner(venue_id=venue.id, staff_id=owner.id))
    return venue


def main() -> None:
    """Seed promotions staff and a test venue into the local database."""
    db = SessionLocal()
    try:
        staff = [_get_or_create_staff(db, email, name) for email, name in PROMOTIONS_STAFF]
        venue = _get_or_create_test_venue(db, owner=staff[0])
        db.commit()
        print(f"Promotions staff: {[s.email for s in staff]}")
        print(f"Test venue: {venue.name!r} (id={venue.id}, owner={staff[0].email})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
