"""User service for profile management and Airtable synchronization."""

import logging
import re
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
import httpx2 as httpx

from app.auth import ACTIVE_STATUS
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.models.job_log import JobLog
from app.config import settings
from app.services.staff_photo_service import (
    delete_photo,
    download_photo,
    photo_exists,
    save_photo,
    select_photo_attachment,
)

logger = logging.getLogger(__name__)

PROMOTIONS_DEPARTMENT = "Promotions"

_SPINITRON_URL_RE = re.compile(r"https://(?:widgets\.)?spinitron\.com/KALX/dj/(\d+)/")


def _format_airtable_name(raw: str) -> str:
    """Convert Airtable 'Last, First (pronouns)' format to 'First Last'."""
    name = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    if "," in name:
        last, first = [p.strip() for p in name.split(",", 1)]
        if first:
            return f"{first} {last}"
    return name


def _extract_pronouns(raw: str) -> Optional[str]:
    """Return the pronouns from Airtable's 'Last, First (pronouns)' Name format, if any."""
    match = re.search(r"\(([^)]*)\)", raw)
    if not match:
        return None
    return match.group(1).strip() or None


def _extract_spinitron_ids(raw: str) -> List[int]:
    """Extract Spinitron persona IDs from Spinitron DJ profile URLs in a markdown string."""
    return [int(m.group(1)) for m in _SPINITRON_URL_RE.finditer(raw)]


class UserService:
    """Service for managing user profiles and Airtable synchronization."""

    @staticmethod
    async def fetch_airtable_records() -> List[Dict[str, Any]]:
        """
        Fetch all records from the Airtable staff directory table.

        Each record is expected to have an "Email address" field and a
        "Department" comma-delimited string field.

        Returns:
            List of Airtable records, each a dict with the record's "id" and
            its "fields" dict

        Raises:
            HTTPException: If Airtable API call fails
        """
        if not settings.airtable_api_key or not settings.airtable_base_id:
            logger.warning("Airtable credentials not configured, returning empty list")
            return []

        url = f"https://api.airtable.com/v0/{settings.airtable_base_id}/{settings.airtable_table_name}"
        headers = {
            "Authorization": f"Bearer {settings.airtable_api_key}",
            "Content-Type": "application/json",
        }

        records = []
        try:
            async with httpx.AsyncClient() as client:
                offset = None
                while True:
                    params = {}
                    if offset:
                        params["offset"] = offset

                    response = await client.get(
                        url, headers=headers, params=params, timeout=30.0
                    )
                    response.raise_for_status()

                    data = response.json()
                    for record in data.get("records", []):
                        records.append(
                            {"id": record.get("id"), "fields": record.get("fields", {})}
                        )

                    offset = data.get("offset")
                    if not offset:
                        break

            logger.info(f"Fetched {len(records)} records from Airtable")
            return records

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Airtable API error: {e.response.status_code} - {e.response.text}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch records from Airtable: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Error fetching records from Airtable: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to fetch records from Airtable: {str(e)}",
            )

    @staticmethod
    async def sync_from_airtable(db: Session, trigger: str = "manual") -> Dict[str, Any]:
        """
        Synchronize users from Airtable into the local database.

        Fetches the "Online Staff App Directory" table (configurable via
        AIRTABLE_TABLE_NAME). Only records whose "Status" includes "Active"
        are imported; the table also lists people who aren't active yet (e.g.
        "🆕"), and they're skipped as if absent. Each record's "Department"
        comma-delimited string
        field determines the role: "Promotions" department maps to the
        promotions_staff table; all other departments map to the staff table.

        Extracts Spinitron persona IDs from URLs in the "DJ Name" column and
        stores them in staff.spinitron_ids. Then calls the Spinitron API to
        resolve the DJ name for each persona ID and stores the result in
        staff.dj_name.

        Existing DB records not present in Airtable (or present but not
        "Active") are left in place so that
        historical show/pass associations are preserved. The one exception is
        the "Active" status: a staff member who no longer appears in Airtable
        as "Active" has their "Active" status removed (see the deactivation step
        below), since access-control checks (`_is_promotions_staff`,
        `get_staff_member`) treat "Active" as a gate. Everything else about
        the record — the Staff row itself, other statuses, departments, venue/
        promoter/specialty-show ownership, passes, lottery entries — is left
        untouched, both because it may still be needed for historical
        display and because none of those foreign keys cascade on delete.

        :returns: Dict with promotions_upserted, staff_upserted, deactivated,
            and errors lists
        """
        result: Dict[str, Any] = {
            "promotions_upserted": [],
            "staff_upserted": [],
            "deactivated": [],
            "errors": [],
            "_trigger": trigger,
        }

        try:
            records = await UserService.fetch_airtable_records()
        except HTTPException as e:
            result["errors"].append(str(e.detail))
            return result

        from app.services.audit_service import log_event

        # (staff ID, "Photo" attachment or None) for each upserted record,
        # reconciled with the photos on disk after the loop.
        photo_updates: List[tuple[int, Optional[Dict[str, Any]]]] = []
        # Emails of the "Active" records Airtable returned, for the
        # deactivation step below.
        seen_emails: set[str] = set()

        for record in records:
            fields = record.get("fields", {})
            record_id = record.get("id")
            email = (
                fields.get("Email address") or fields.get("email") or fields.get("Email")
            )
            if not email or not isinstance(email, str):
                continue
            email = email.strip().lower()

            statuses = fields.get("Status", [])
            if isinstance(statuses, str):
                statuses = [s.strip() for s in statuses.split(",")]
            elif not isinstance(statuses, list):
                statuses = []
            if ACTIVE_STATUS not in statuses:
                continue
            seen_emails.add(email)

            raw_name = (fields.get("Name") or "").strip()
            name = _format_airtable_name(raw_name)
            pronouns = _extract_pronouns(raw_name)
            phone = (fields.get("Phone") or "").strip()
            titles_and_roles = fields.get("Titles and Roles")
            if not isinstance(titles_and_roles, str) or not titles_and_roles.strip():
                titles_and_roles = None
            else:
                titles_and_roles = titles_and_roles.strip()
            photo_attachment = select_photo_attachment(fields.get("Photo"))

            departments = fields.get("Department", [])
            if isinstance(departments, str):
                departments = [d.strip() for d in departments.split(",")]
            elif not isinstance(departments, list):
                departments = []

            # Extract Spinitron persona IDs from URLs in the "DJ Name" field
            raw_dj_field = fields.get("DJ Name", "")
            spinitron_ids: Optional[List[int]] = None
            if raw_dj_field and isinstance(raw_dj_field, str):
                ids = _extract_spinitron_ids(raw_dj_field)
                if ids:
                    spinitron_ids = ids

            try:
                # Everyone goes into the staff table. Match on the Airtable
                # record ID so an email change in Airtable updates the existing
                # row; rows synced before record IDs were stored match by email.
                existing_staff = None
                if record_id:
                    existing_staff = (
                        db.query(Staff)
                        .filter(Staff.airtable_record_id == record_id)
                        .first()
                    )
                if existing_staff is None:
                    existing_staff = db.query(Staff).filter(Staff.email == email).first()
                elif existing_staff.email != email:
                    email_taken = (
                        db.query(Staff)
                        .filter(Staff.email == email, Staff.id != existing_staff.id)
                        .first()
                    )
                    if email_taken:
                        error_msg = (
                            f"Can't change {existing_staff.email} to {email}: another "
                            "staff record already has that email"
                        )
                        logger.error(error_msg)
                        result["errors"].append(error_msg)
                        continue
                if existing_staff:
                    # Detect field changes for audit logging
                    changed: Dict[str, Any] = {}
                    if existing_staff.email != email:
                        changed["email"] = {"before": existing_staff.email, "after": email}
                    if existing_staff.name != name:
                        changed["name"] = {"before": existing_staff.name, "after": name}
                    if existing_staff.phone != phone:
                        changed["phone"] = {"before": existing_staff.phone, "after": phone}
                    old_ids = existing_staff.spinitron_ids or []
                    new_ids = spinitron_ids or []
                    if old_ids != new_ids:
                        changed["spinitron_ids"] = {"before": old_ids, "after": new_ids}
                    if existing_staff.pronouns != pronouns:
                        changed["pronouns"] = {
                            "before": existing_staff.pronouns,
                            "after": pronouns,
                        }
                    if existing_staff.titles_and_roles != titles_and_roles:
                        changed["titles_and_roles"] = {
                            "before": existing_staff.titles_and_roles,
                            "after": titles_and_roles,
                        }
                    existing_staff.email = email
                    existing_staff.name = name
                    existing_staff.pronouns = pronouns
                    existing_staff.phone = phone
                    existing_staff.titles_and_roles = titles_and_roles
                    existing_staff.spinitron_ids = spinitron_ids
                    if record_id:
                        existing_staff.airtable_record_id = record_id
                    staff_record = existing_staff
                    is_new = False
                else:
                    staff_record = Staff(
                        airtable_record_id=record_id,
                        email=email,
                        name=name,
                        pronouns=pronouns,
                        phone=phone,
                        titles_and_roles=titles_and_roles,
                        spinitron_ids=spinitron_ids,
                    )
                    db.add(staff_record)
                    db.flush()
                    changed = {}
                    is_new = True
                result["staff_upserted"].append(email)

                # Sync department memberships
                existing_depts = {
                    d.department
                    for d in (
                        db.query(StaffDepartment)
                        .filter(StaffDepartment.staff_id == staff_record.id)
                        .all()
                    )
                }
                depts_added = []
                depts_removed = []
                for dept in departments:
                    if dept and dept not in existing_depts:
                        db.add(StaffDepartment(staff_id=staff_record.id, department=dept))
                        depts_added.append(dept)
                # Remove departments no longer present
                for old_dept in existing_depts:
                    if old_dept not in departments:
                        db.query(StaffDepartment).filter(
                            StaffDepartment.staff_id == staff_record.id,
                            StaffDepartment.department == old_dept,
                        ).delete()
                        depts_removed.append(old_dept)

                if depts_added:
                    changed["departments_added"] = depts_added
                if depts_removed:
                    changed["departments_removed"] = depts_removed

                # Sync status values
                existing_statuses = {
                    s.status
                    for s in (
                        db.query(StaffStatus)
                        .filter(StaffStatus.staff_id == staff_record.id)
                        .all()
                    )
                }
                statuses_added = []
                statuses_removed = []
                for stat in statuses:
                    if stat and stat not in existing_statuses:
                        db.add(StaffStatus(staff_id=staff_record.id, status=stat))
                        statuses_added.append(stat)
                for old_stat in existing_statuses:
                    if old_stat not in statuses:
                        db.query(StaffStatus).filter(
                            StaffStatus.staff_id == staff_record.id,
                            StaffStatus.status == old_stat,
                        ).delete()
                        statuses_removed.append(old_stat)

                if statuses_added:
                    changed["statuses_added"] = statuses_added
                if statuses_removed:
                    changed["statuses_removed"] = statuses_removed

                # Track promotions department members for the result summary
                if PROMOTIONS_DEPARTMENT in departments:
                    result["promotions_upserted"].append(email)

                db.commit()
                photo_updates.append((staff_record.id, photo_attachment))

                # Audit log after successful commit
                if is_new:
                    log_event(
                        db,
                        event_type="airtable_sync_added",
                        actor_role="system",
                        entity_type="staff",
                        entity_id=staff_record.id,
                        details={"email": email, "name": name, "departments": departments},
                    )
                elif changed:
                    log_event(
                        db,
                        event_type="airtable_sync_changed",
                        actor_role="system",
                        entity_type="staff",
                        entity_id=staff_record.id,
                        details={"email": email, "changes": changed},
                    )
            except SQLAlchemyError as e:
                db.rollback()
                error_msg = f"DB error upserting {email}: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)

        # Deactivate staff who no longer appear in Airtable as "Active". The
        # loop above only reconciles departments/statuses for the Active
        # records Airtable returned, so someone removed from the table, or no
        # longer Active in it, would otherwise keep whatever access they
        # already had, indefinitely.
        # Guarded on a non-empty `seen_emails`: if Airtable returned nothing
        # (e.g. credentials misconfigured — see fetch_airtable_records), an
        # empty set here would otherwise match every "Active" staff member
        # and deactivate the entire directory.
        if seen_emails:
            vanished = (
                db.query(Staff)
                .join(StaffStatus, Staff.id == StaffStatus.staff_id)
                .filter(StaffStatus.status == ACTIVE_STATUS, ~Staff.email.in_(seen_emails))
                .all()
            )
            for staff_record in vanished:
                try:
                    db.query(StaffStatus).filter(
                        StaffStatus.staff_id == staff_record.id,
                        StaffStatus.status == ACTIVE_STATUS,
                    ).delete()
                    db.commit()
                    result["deactivated"].append(staff_record.email)
                    log_event(
                        db,
                        event_type="airtable_sync_deactivated",
                        actor_role="system",
                        entity_type="staff",
                        entity_id=staff_record.id,
                        details={
                            "email": staff_record.email,
                            "reason": "no longer Active in Airtable",
                        },
                    )
                except SQLAlchemyError as e:
                    db.rollback()
                    error_msg = f"DB error deactivating {staff_record.email}: {str(e)}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)

        # Phase 2: Resolve DJ names from Spinitron API
        if settings.spinitron_api_key and result["staff_upserted"]:
            from app.services.spinitron_service import SpinitronService

            try:
                persona_map = await SpinitronService.fetch_all_personas()
                for email in result["staff_upserted"]:
                    staff_record = db.query(Staff).filter(Staff.email == email).first()
                    if staff_record is None:
                        continue
                    ids = staff_record.spinitron_ids or []
                    personas = [
                        {"id": sid, "name": persona_map[sid]}
                        for sid in ids
                        if sid in persona_map
                    ]
                    staff_record.dj_name = (
                        ", ".join(p["name"] for p in personas) if personas else None
                    )
                    staff_record.dj_personas = personas or None
                db.commit()
                logger.info(
                    "Updated DJ names from Spinitron for %d staff records",
                    len(result["staff_upserted"]),
                )
            except Exception as e:
                db.rollback()
                error_msg = f"Spinitron DJ name resolution failed: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)

        # Phase 3: Bring the staff directory photos on disk up to date
        await UserService._sync_photos(db, photo_updates, result)

        # Record sync event for admin display
        try:
            db.add(
                JobLog(
                    job_id="airtable_user_sync", trigger=result.get("_trigger", "manual")
                )
            )
            db.commit()
        except Exception:
            db.rollback()

        logger.info(
            f"Sync completed: {len(result['promotions_upserted'])} promotions, "
            f"{len(result['staff_upserted'])} staff, {len(result['deactivated'])} "
            f"deactivated, {len(result['errors'])} errors"
        )
        return result

    @staticmethod
    async def _sync_photos(
        db: Session,
        photo_updates: List[tuple[int, Optional[Dict[str, Any]]]],
        result: Dict[str, Any],
    ) -> None:
        """
        Download new or changed staff photos from Airtable and remove deleted ones.

        A photo is downloaded only when its Airtable attachment ID differs from
        the one stored on the staff record, or its files are missing from disk.
        A failed download leaves the previous photo, if any, in place so the
        next sync retries it.

        :param db: Database session.
        :param photo_updates: (staff ID, "Photo" attachment or None) pairs.
        :param result: Sync result dict; failures are added to its "errors".
        """
        for staff_id, attachment in photo_updates:
            staff_record = db.get(Staff, staff_id)
            if staff_record is None:
                continue

            if attachment is None:
                if staff_record.photo_attachment_id:
                    delete_photo(staff_id)
                    staff_record.photo_attachment_id = None
                    db.commit()
                continue

            if staff_record.photo_attachment_id == attachment["id"] and photo_exists(
                staff_id
            ):
                continue

            try:
                image_bytes = await download_photo(attachment["url"])
                save_photo(staff_id, image_bytes)
            except Exception as e:
                error_msg = f"Failed to update photo for {staff_record.email}: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
                continue

            staff_record.photo_attachment_id = attachment["id"]
            db.commit()

    @staticmethod
    def get_or_create_profile(db: Session, email: str) -> Staff:
        """
        Get or create a staff profile by email.

        Used for both promotions-department members and general staff — the
        underlying `Staff` row is identical either way.

        Args:
            db: Database session
            email: User email from authentication

        Returns:
            Staff profile

        Raises:
            HTTPException: If database error occurs
        """
        try:
            profile = db.query(Staff).filter(Staff.email == email).first()
            if profile:
                return profile

            profile = Staff(email=email, name="", phone="")
            db.add(profile)
            db.commit()
            db.refresh(profile)
            return profile
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error getting/creating profile for {email}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while accessing profile",
            )
