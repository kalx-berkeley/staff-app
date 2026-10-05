"""Tests for the Staff Directory API and the Airtable sync fields it relies on."""

from datetime import date
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app import config
from app.models.audit_log import AuditLog
from app.models.impersonation_session import ImpersonationSession
from app.models.staff import Staff
from app.models.staff_department import StaffDepartment
from app.models.staff_status import StaffStatus
from app.services.staff_photo_service import photo_path


def _make_staff(
    db: Session,
    email: str,
    name: str,
    statuses: tuple[str, ...] = ("Active",),
    departments: tuple[str, ...] = (),
    **columns,
) -> Staff:
    staff = Staff(email=email, name=name, phone="510-555-0100", **columns)
    db.add(staff)
    db.flush()
    for status in statuses:
        db.add(StaffStatus(staff_id=staff.id, status=status))
    for department in departments:
        db.add(StaffDepartment(staff_id=staff.id, department=department))
    db.commit()
    return staff


def _jpeg_bytes(size: tuple[int, int] = (600, 800)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _heic_bytes(size: tuple[int, int] = (600, 800)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (30, 30, 200)).save(buffer, format="HEIF")
    return buffer.getvalue()


@pytest.fixture
def photo_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "staff_photo_dir", str(tmp_path))
    return tmp_path


def _as(email: str) -> dict:
    return {"X-Forwarded-User": email}


# --- GET /api/directory ---


def test_directory_lists_active_staff_sorted_by_name(client: TestClient, db: Session):
    _make_staff(
        db,
        "zed@example.com",
        "Zed Zulu",
        statuses=("Active", "Paid Staff"),
        departments=("Music", "News"),
        pronouns="he/him",
        titles_and_roles="News Director\nOffice hours: Tue 2-4",
        dj_name="DJ Zed, Zed, Esq.",
        spinitron_ids=[123, 456],
        dj_personas=[{"id": 123, "name": "DJ Zed"}, {"id": 456, "name": "Zed, Esq."}],
        photo_attachment_id="attA",
    )
    _make_staff(db, "amy@example.com", "amy Adams")
    _make_staff(db, "gone@example.com", "Gone Person", statuses=("Sublist DJ",))

    response = client.get("/api/directory", headers=_as("amy@example.com"))

    assert response.status_code == 200
    entries = response.json()
    assert [e["name"] for e in entries] == ["amy Adams", "Zed Zulu"]
    zed = entries[1]
    assert zed["email"] == "zed@example.com"
    assert zed["phone"] == "510-555-0100"
    assert zed["pronouns"] == "he/him"
    assert zed["titles_and_roles"] == "News Director\nOffice hours: Tue 2-4"
    assert zed["dj_name"] == "DJ Zed, Zed, Esq."
    assert zed["dj_personas"] == [
        {"id": 123, "name": "DJ Zed"},
        {"id": 456, "name": "Zed, Esq."},
    ]
    assert zed["departments"] == ["Music", "News"]
    assert zed["statuses"] == ["Active", "Paid Staff"]
    assert zed["photo_version"] == "attA"
    assert entries[0]["photo_version"] is None


def test_directory_shows_leave_dates_until_the_leave_ends(client: TestClient, db: Session):
    _make_staff(
        db,
        "now@example.com",
        "Now Leave",
        loa_start=date(2000, 1, 1),
        loa_end=date(2999, 1, 1),
    )
    _make_staff(db, "past@example.com", "Past Leave", loa_end=date(2000, 1, 1))

    entries = {
        e["name"]: e
        for e in client.get("/api/directory", headers=_as("now@example.com")).json()
    }

    assert entries["Now Leave"]["on_leave"] is True
    assert entries["Now Leave"]["loa_start"] == "2000-01-01"
    assert entries["Past Leave"]["loa_end"] is None


def test_directory_shows_past_leave_dates_for_on_leave_status(
    client: TestClient, db: Session
):
    _make_staff(
        db,
        "eve@example.com",
        "Eve Ellis",
        statuses=("Active", "On leave"),
        loa_start=date(2000, 1, 1),
        loa_end=date(2000, 2, 1),
    )

    eve = client.get("/api/directory", headers=_as("eve@example.com")).json()[0]

    assert eve["on_leave"] is False
    assert eve["loa_start"] == "2000-01-01"
    assert eve["loa_end"] == "2000-02-01"


@pytest.mark.parametrize(
    "dj_name, spinitron_ids, expected",
    [
        ("DJ Zed", [123], [{"id": 123, "name": "DJ Zed"}]),
        ("Zed, Esq.", [123], [{"id": 123, "name": "Zed, Esq."}]),
        (
            "DJ Zed, DJ Z",
            [123, 456],
            [{"id": 123, "name": "DJ Zed"}, {"id": 456, "name": "DJ Z"}],
        ),
        # One persona wasn't found in Spinitron, so the names can't be paired up
        ("DJ Zed", [123, 456], []),
        (None, [123], []),
    ],
)
def test_directory_pairs_dj_names_for_records_without_dj_personas(
    client: TestClient, db: Session, dj_name, spinitron_ids, expected
):
    _make_staff(
        db, "zed@example.com", "Zed Zulu", dj_name=dj_name, spinitron_ids=spinitron_ids
    )

    response = client.get("/api/directory", headers=_as("zed@example.com"))

    assert response.json()[0]["dj_personas"] == expected


@pytest.mark.parametrize("email", ["gone@example.com", "stranger@example.com"])
def test_directory_rejects_anyone_not_active(client: TestClient, db: Session, email):
    _make_staff(db, "gone@example.com", "Gone Person", statuses=("Sublist DJ",))

    response = client.get("/api/directory", headers=_as(email))

    assert response.status_code == 403


def test_directory_follows_impersonation(client: TestClient, db: Session, monkeypatch):
    monkeypatch.setattr(config.settings, "environment", "staging")
    _make_staff(db, "promo@example.com", "Promo Person", departments=("Promotions",))
    _make_staff(db, "gone@example.com", "Gone Person", statuses=())
    db.add(
        ImpersonationSession(
            real_email="promo@example.com", impersonated_email="gone@example.com"
        )
    )
    db.commit()

    response = client.get("/api/directory", headers=_as("promo@example.com"))

    assert response.status_code == 403


def test_directory_is_rate_limited(client: TestClient, db: Session):
    _make_staff(db, "amy@example.com", "Amy Adams")

    statuses = [
        client.get("/api/directory", headers=_as("amy@example.com")).status_code
        for _ in range(31)
    ]

    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429


# --- GET /api/directory/{id}/photo ---


def test_photo_is_served_to_active_staff(client: TestClient, db: Session, photo_dir):
    from app.services.staff_photo_service import save_photo

    staff = _make_staff(db, "amy@example.com", "Amy Adams", photo_attachment_id="attA")
    save_photo(staff.id, _jpeg_bytes())

    thumb = client.get(f"/api/directory/{staff.id}/photo", headers=_as("amy@example.com"))
    medium = client.get(
        f"/api/directory/{staff.id}/photo?size=medium", headers=_as("amy@example.com")
    )

    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"
    assert Image.open(BytesIO(thumb.content)).size == (128, 128)
    assert Image.open(BytesIO(medium.content)).size == (360, 480)


def test_photo_404s_without_a_photo_or_for_inactive_staff(
    client: TestClient, db: Session, photo_dir
):
    from app.services.staff_photo_service import save_photo

    _make_staff(db, "amy@example.com", "Amy Adams")
    no_photo = _make_staff(db, "bob@example.com", "Bob Brown")
    gone = _make_staff(
        db, "gone@example.com", "Gone Person", statuses=(), photo_attachment_id="attG"
    )
    save_photo(gone.id, _jpeg_bytes())

    for staff_id in (no_photo.id, gone.id):
        response = client.get(
            f"/api/directory/{staff_id}/photo", headers=_as("amy@example.com")
        )
        assert response.status_code == 404


def test_photo_requires_active_viewer(client: TestClient, db: Session, photo_dir):
    staff = _make_staff(db, "amy@example.com", "Amy Adams", photo_attachment_id="attA")

    response = client.get(
        f"/api/directory/{staff.id}/photo", headers=_as("stranger@example.com")
    )

    assert response.status_code == 403


# --- Airtable sync ---


def _sync(client: TestClient, records: list[dict], download=None):
    download = download or AsyncMock(return_value=_jpeg_bytes())
    with (
        patch(
            "app.services.user_service.UserService.fetch_airtable_records",
            new_callable=AsyncMock,
            return_value=records,
        ),
        patch("app.services.user_service.download_photo", download),
    ):
        response = client.post("/api/users/sync", headers=_as("admin@example.com"))
    assert response.status_code == 200
    return response.json()


def _admin_record() -> dict:
    return {
        "id": "recAdmin",
        "fields": {
            "Email address": "admin@example.com",
            "Name": "Admin, Ada",
            "Department": ["Promotions"],
            "Status": ["Active"],
        },
    }


def test_sync_stores_pronouns_titles_and_record_id(
    client: TestClient, db: Session, photo_dir
):
    _make_staff(db, "admin@example.com", "Ada Admin", departments=("Promotions",))

    _sync(
        client,
        [
            _admin_record(),
            {
                "id": "recJane",
                "fields": {
                    "Email address": "Jane@Example.com",
                    "Name": "Doe, Jane (she/they)",
                    "First Name": " Jane ",
                    "Surname": "Doe",
                    "Pronouns": "she/they",
                    "Titles and Roles": "  Music Director\nOffice hours: Mon 1-3 \n",
                    "Status": ["Active"],
                },
            },
        ],
    )

    jane = db.query(Staff).filter_by(email="jane@example.com").one()
    assert jane.name == "Jane Doe"
    assert jane.pronouns == "she/they"
    assert jane.titles_and_roles == "Music Director\nOffice hours: Mon 1-3"
    assert jane.airtable_record_id == "recJane"
    admin = db.query(Staff).filter_by(email="admin@example.com").one()
    assert admin.pronouns is None
    assert admin.titles_and_roles is None
    assert admin.airtable_record_id == "recAdmin"


def test_sync_falls_back_to_name_when_first_name_and_surname_are_blank(
    client: TestClient, db: Session, photo_dir
):
    _make_staff(db, "admin@example.com", "Ada Admin", departments=("Promotions",))

    _sync(
        client,
        [
            _admin_record(),
            {
                "id": "recMono",
                "fields": {
                    "Email address": "mono@example.com",
                    "Name": "Mononym (they/them)",
                    "First Name": "",
                    "Status": ["Active"],
                },
            },
            {
                "id": "recFirst",
                "fields": {
                    "Email address": "first@example.com",
                    "Name": "Only, First",
                    "First Name": "First",
                    "Status": ["Active"],
                },
            },
        ],
    )

    mono = db.query(Staff).filter_by(email="mono@example.com").one()
    # Name is used as-is, and pronouns come only from the Pronouns column.
    assert mono.name == "Mononym (they/them)"
    assert mono.pronouns is None
    assert db.query(Staff).filter_by(email="first@example.com").one().name == "First"


def test_sync_stores_and_audits_leave_of_absence(
    client: TestClient, db: Session, photo_dir
):
    _make_staff(db, "admin@example.com", "Ada Admin", departments=("Promotions",))
    jane = _make_staff(db, "jane@example.com", "Jane Doe", airtable_record_id="recJane")
    jane.loa_end = date(2026, 1, 31)
    db.commit()

    _sync(
        client,
        [
            _admin_record(),
            {
                "id": "recJane",
                "fields": {
                    "Email address": "jane@example.com",
                    "First Name": "Jane",
                    "Surname": "Doe",
                    "LOA start": "2027-03-01",
                    "LOA end": "not a date",
                    "Status": ["Active"],
                },
            },
        ],
    )

    db.expire_all()
    jane = db.get(Staff, jane.id)
    assert jane.loa_start == date(2027, 3, 1)
    assert jane.loa_end is None
    event = (
        db.query(AuditLog)
        .filter_by(event_type="airtable_sync_changed", entity_id=jane.id)
        .one()
    )
    assert event.details["changes"]["loa_start"] == {"before": None, "after": "2027-03-01"}
    assert event.details["changes"]["loa_end"] == {"before": "2026-01-31", "after": None}


def test_sync_follows_an_email_change_by_record_id(
    client: TestClient, db: Session, photo_dir
):
    _make_staff(db, "admin@example.com", "Ada Admin", departments=("Promotions",))
    jane = _make_staff(db, "old@example.com", "Jane Doe", airtable_record_id="recJane")

    _sync(
        client,
        [
            _admin_record(),
            {
                "id": "recJane",
                "fields": {
                    "Email address": "new@example.com",
                    "Name": "Doe, Jane",
                    "Status": ["Active"],
                },
            },
        ],
    )

    db.expire_all()
    assert db.get(Staff, jane.id).email == "new@example.com"
    assert db.query(Staff).filter_by(email="old@example.com").first() is None


def test_sync_reports_an_email_change_that_collides(
    client: TestClient, db: Session, photo_dir
):
    _make_staff(db, "admin@example.com", "Ada Admin", departments=("Promotions",))
    jane = _make_staff(db, "old@example.com", "Jane Doe", airtable_record_id="recJane")
    _make_staff(db, "taken@example.com", "Someone Else")

    result = _sync(
        client,
        [
            _admin_record(),
            {
                "id": "recJane",
                "fields": {"Email address": "taken@example.com", "Status": ["Active"]},
            },
        ],
    )

    db.expire_all()
    assert db.get(Staff, jane.id).email == "old@example.com"
    assert any("taken@example.com" in error for error in result["errors"])


def test_sync_downloads_photos_only_when_they_change(
    client: TestClient, db: Session, photo_dir
):
    _make_staff(db, "admin@example.com", "Ada Admin", departments=("Promotions",))

    def records(photo):
        admin = _admin_record()
        if photo is not None:
            admin["fields"]["Photo"] = photo
        return [admin]

    attachment = [{"id": "attOne", "url": "https://example.com/1", "type": "image/jpeg"}]
    download = AsyncMock(return_value=_jpeg_bytes())

    _sync(client, records(attachment), download)
    _sync(client, records(attachment), download)

    admin = db.query(Staff).filter_by(email="admin@example.com").one()
    assert download.await_count == 1
    download.assert_awaited_with("https://example.com/1")
    assert admin.photo_attachment_id == "attOne"
    assert photo_path(admin.id, "thumb").is_file()
    assert photo_path(admin.id, "medium").is_file()

    _sync(client, records(None), download)

    db.expire_all()
    assert db.get(Staff, admin.id).photo_attachment_id is None
    assert not photo_path(admin.id, "thumb").exists()
    assert not photo_path(admin.id, "medium").exists()


def test_sync_keeps_the_old_photo_when_a_download_fails(
    client: TestClient, db: Session, photo_dir
):
    admin = _make_staff(
        db,
        "admin@example.com",
        "Ada Admin",
        departments=("Promotions",),
        photo_attachment_id="attOld",
    )
    from app.services.staff_photo_service import save_photo

    save_photo(admin.id, _jpeg_bytes())
    record = _admin_record()
    record["fields"]["Photo"] = [{"id": "attNew", "url": "https://example.com/new"}]

    result = _sync(client, [record], AsyncMock(side_effect=RuntimeError("boom")))

    db.expire_all()
    assert db.get(Staff, admin.id).photo_attachment_id == "attOld"
    assert photo_path(admin.id, "thumb").is_file()
    assert any("admin@example.com" in error for error in result["errors"])


def test_heic_photos_are_converted_to_jpeg(photo_dir):
    from app.services.staff_photo_service import save_photo

    save_photo(7, _heic_bytes())

    with Image.open(photo_path(7, "thumb")) as thumb:
        assert thumb.format == "JPEG"
        assert thumb.size == (128, 128)
    with Image.open(photo_path(7, "medium")) as medium:
        assert medium.format == "JPEG"
        assert medium.size == (360, 480)
