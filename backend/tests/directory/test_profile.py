"""Tests for the Staff Directory's profile page API and DJ Quiz deadline settings."""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app import config
from app.directory.services import profile as profile_service
from app.models.audit_log import AuditLog
from app.models.dj_quiz_deadline import DjQuizDeadline
from app.models.dj_shift_playlist import DjShiftPlaylist
from app.models.impersonation_session import ImpersonationSession
from app.models.job_log import JobLog
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_spinitron_show import SpecialtyShowSpinitronShow
from app.models.staff import Staff
from app.models.staff_status import StaffStatus
from app.models.workform_airtable_record import WorkformAirtableRecord

TODAY = date(2026, 10, 20)
DJ_ID = "recDJ0000000000AA"


def _make_staff(
    db: Session, email: str, name: str, statuses=("Active",), **columns
) -> Staff:
    staff = Staff(email=email, name=name, phone=columns.pop("phone", ""), **columns)
    db.add(staff)
    db.flush()
    for status in statuses:
        db.add(StaffStatus(staff_id=staff.id, status=status))
    db.commit()
    return staff


def _as(email: str) -> dict:
    return {"X-Forwarded-User": email}


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(profile_service, "today_pt", lambda: TODAY)
    monkeypatch.setattr("app.directory.routers.directory.today_pt", lambda: TODAY)


@pytest.fixture
def editing(monkeypatch):
    monkeypatch.setattr(config.settings, "directory_self_edit_enabled", True)


@pytest.fixture
def personas():
    with patch(
        "app.directory.services.profile.cached_persona_names",
        new_callable=AsyncMock,
        return_value={111: "DJ Zed", 222: "Zed, Esq.", 176287: "DJ Trainee"},
    ) as mock:
        yield mock


@pytest.fixture
def dj(db: Session) -> Staff:
    return _make_staff(
        db,
        "dj@example.com",
        "Zed Zulu",
        statuses=("Active", "Sublist DJ"),
        airtable_record_id=DJ_ID,
        first_name="Zed",
        surname="Zulu",
        pronouns="he/him",
        phone="(510) 555-0100",
        spinitron_ids=[111],
        dj_name="DJ Zed",
        dj_personas=[{"id": 111, "name": "DJ Zed"}],
        dj_quiz_years=[2025, 2026],
    )


def _pacific(year, month, day, hour) -> datetime:
    return datetime(year, month, day, hour + 7, tzinfo=timezone.utc)


def _add_playlist(db, pid, start, minutes, persona_id=111, show_id=None, automation=False):
    db.add(
        DjShiftPlaylist(
            id=pid,
            persona_id=persona_id,
            show_id=show_id,
            start=start,
            end=start + timedelta(minutes=minutes),
            title="Night Moves",
            automation=automation,
        )
    )


def _add_workform(db, month: date, hours: dict, record_id: str):
    db.add(
        WorkformAirtableRecord(
            airtable_record_id=record_id,
            staff_airtable_record_id=DJ_ID,
            month=month,
            created_time=datetime(month.year, month.month, 2, tzinfo=timezone.utc),
            departments={
                dept: {"hours": h, "description": "Work", "approved": decision}
                for dept, (h, decision) in hours.items()
            },
        )
    )


def _make_eligible(db: Session):
    db.add(DjQuizDeadline(year=2025, deadline=date(2025, 7, 31)))
    db.add(DjQuizDeadline(year=2026, deadline=date(2026, 9, 30)))
    _add_playlist(db, 1, _pacific(2026, 6, 3, 10), 120)
    db.add(JobLog(job_id="dj_shift_sync", trigger="scheduled"))
    _add_workform(db, date(2026, 7, 1), {"Music": (6, "Approved")}, "recW1")
    _add_workform(db, date(2026, 8, 1), {"Music": (7, "Approved")}, "recW2")
    _add_workform(db, date(2026, 9, 1), {"Music": (6, None)}, "recW3")
    db.commit()


# --- Seeing a profile ---


def test_my_profile(client: TestClient, db: Session, dj):
    response = client.get("/api/directory/me/profile", headers=_as("dj@example.com"))
    assert response.status_code == 200
    profile = response.json()
    assert profile["entry"]["name"] == "Zed Zulu"
    assert profile["entry"]["dj_quiz_years"] == [2025, 2026]
    assert profile["first_name"] == "Zed"
    assert profile["is_self"] is True
    assert profile["can_edit"] is False
    assert len(profile["workforms"]) == 12
    assert profile["workforms"][0]["month"] == "2026-10"
    assert profile["eligibility"] is not None


def test_the_profile_always_shows_a_past_leave(client: TestClient, db: Session, dj):
    dj.loa_start, dj.loa_end = date(2025, 1, 1), date(2025, 3, 1)
    db.commit()
    profile = client.get("/api/directory/me/profile", headers=_as("dj@example.com")).json()
    assert profile["loa_end"] == "2025-03-01"
    # The sidebar's entry keeps the directory's rule
    assert profile["entry"]["loa_end"] is None


def test_no_checklist_without_a_persona_or_sublist_status(client: TestClient, db: Session):
    _make_staff(db, "amy@example.com", "Amy Adams")
    profile = client.get("/api/directory/me/profile", headers=_as("amy@example.com")).json()
    assert profile["eligibility"] is None


def test_other_staff_cant_see_a_profile(client: TestClient, db: Session, dj):
    _make_staff(db, "amy@example.com", "Amy Adams")
    response = client.get(f"/api/directory/{dj.id}/profile", headers=_as("amy@example.com"))
    assert response.status_code == 403


def test_site_admins_can_see_anyones_profile(client: TestClient, db: Session, dj):
    _make_staff(db, "boss@example.com", "Boss", statuses=("Active", "Paid Staff"))
    response = client.get(
        f"/api/directory/{dj.id}/profile", headers=_as("boss@example.com")
    )
    assert response.status_code == 200
    assert response.json()["is_self"] is False
    assert response.json()["eligibility"] is not None


def test_the_real_user_decides_site_admin_access(
    client: TestClient, db: Session, dj, monkeypatch
):
    monkeypatch.setattr(config.settings, "environment", "staging")
    _make_staff(db, "boss@example.com", "Boss", statuses=("Active", "Paid Staff"))
    _make_staff(db, "amy@example.com", "Amy Adams")
    db.add(
        ImpersonationSession(
            real_email="boss@example.com", impersonated_email="amy@example.com"
        )
    )
    db.commit()
    response = client.get(
        f"/api/directory/{dj.id}/profile", headers=_as("boss@example.com")
    )
    assert response.status_code == 200
    me = client.get("/api/directory/me/profile", headers=_as("boss@example.com")).json()
    assert me["entry"]["name"] == "Amy Adams"


def test_a_profile_of_someone_not_current_is_not_found(client: TestClient, db: Session):
    _make_staff(db, "boss@example.com", "Boss", statuses=("Active", "Paid Staff"))
    gone = _make_staff(db, "gone@example.com", "Gone", statuses=("Sublist DJ",))
    response = client.get(
        f"/api/directory/{gone.id}/profile", headers=_as("boss@example.com")
    )
    assert response.status_code == 404


# --- Eligibility ---


def test_an_eligible_sublist_dj(client: TestClient, db: Session, dj):
    _make_eligible(db)
    elig = client.get("/api/directory/me/profile", headers=_as("dj@example.com")).json()[
        "eligibility"
    ]
    assert elig["eligible"] is True
    assert elig["unmet"] == 0
    assert elig["eligible_until"] == "2026-10-31"
    assert elig["shift"]["met"] is True
    assert (
        elig["shift"]["summary"] == "Last qualifying shift: Jun 3, 2026, Night Moves, 2 h"
    )
    assert elig["shift"]["previous_quarter"] == "May–Jul 2026"
    assert elig["workforms"]["summary"] == "Jul 6 h ✓, Aug 7 h ✓, Sep 6 h ✓"
    assert elig["quiz"]["met"] is True
    assert elig["next_workform_note"].startswith("Keep reporting 6 h a month: October")


def test_a_specialty_show_doesnt_count_as_a_shift(client: TestClient, db: Session, dj):
    _make_eligible(db)
    db.query(DjShiftPlaylist).update({"show_id": 301137})
    show = SpecialtyShow(name="Take Five")
    db.add(show)
    db.flush()
    db.add(SpecialtyShowSpinitronShow(specialty_show_id=show.id, spinitron_show_id=301137))
    show.retired_at = datetime(2026, 9, 1)
    db.commit()
    elig = client.get("/api/directory/me/profile", headers=_as("dj@example.com")).json()[
        "eligibility"
    ]
    assert elig["shift"]["met"] is False
    assert elig["shift"]["playlists"][0]["reason"] == "specialty"
    assert elig["eligible"] is False
    assert elig["eligible_until"] is None


def test_a_deleted_specialty_shows_id_is_ignored(client: TestClient, db: Session, dj):
    _make_eligible(db)
    db.query(DjShiftPlaylist).update({"show_id": 301137})
    show = SpecialtyShow(name="Mistake", deleted=True)
    db.add(show)
    db.flush()
    db.add(SpecialtyShowSpinitronShow(specialty_show_id=show.id, spinitron_show_id=301137))
    db.commit()
    elig = client.get("/api/directory/me/profile", headers=_as("dj@example.com")).json()[
        "eligibility"
    ]
    assert elig["shift"]["met"] is True


def test_unmet_requirements(client: TestClient, db: Session, dj):
    _make_eligible(db)
    dj.dj_quiz_years = [2025]
    dj.loa_start = date(2026, 10, 1)
    db.query(WorkformAirtableRecord).filter(
        WorkformAirtableRecord.airtable_record_id == "recW2"
    ).update({"departments": {"Music": {"hours": 7, "approved": None}}})
    db.commit()
    elig = client.get("/api/directory/me/profile", headers=_as("dj@example.com")).json()[
        "eligibility"
    ]
    assert elig["eligible"] is False
    assert elig["unmet"] == 3
    assert elig["leave"]["met"] is False
    assert elig["quiz"]["met"] is False
    august = next(m for m in elig["workforms"]["months"] if m["month"] == "2026-08")
    assert august["met"] is False
    assert august["pending_departments"] == ["Music"]


def test_shifts_not_yet_synced_are_unavailable(client: TestClient, db: Session, dj):
    elig = client.get("/api/directory/me/profile", headers=_as("dj@example.com")).json()[
        "eligibility"
    ]
    assert elig["shift"]["met"] is None
    assert elig["unavailable"] == 1


# --- Editing ---

_UPDATE = {
    "first_name": " Zed ",
    "surname": "Zulu",
    "pronouns": "they/them",
    "phone": "510.555.0199",
    "dj_persona_ids": [111, 222],
}


def test_editing_is_off_by_default(client: TestClient, db: Session, dj):
    response = client.patch(
        f"/api/directory/{dj.id}/profile", json=_UPDATE, headers=_as("dj@example.com")
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Editing isn't available yet"


def test_saving_a_profile_writes_changed_fields_to_airtable(
    client: TestClient, db: Session, dj, editing, personas
):
    with (
        patch(
            "app.common.services.staff_airtable.update_staff_record", new_callable=AsyncMock
        ) as update,
        patch(
            "app.common.services.user_service.UserService.sync_one", new_callable=AsyncMock
        ) as sync_one,
    ):
        response = client.patch(
            f"/api/directory/{dj.id}/profile", json=_UPDATE, headers=_as("dj@example.com")
        )
    assert response.status_code == 200, response.text
    assert response.json()["can_edit"] is True
    update.assert_awaited_once_with(
        DJ_ID,
        {
            "Pronouns": "they/them",
            "Phone": "(510) 555-0199",
            "DJ Name": (
                "[DJ Zed](https://spinitron.com/KALX/dj/111/), "
                "[Zed, Esq.](https://spinitron.com/KALX/dj/222/)"
            ),
        },
    )
    sync_one.assert_awaited_once()
    entry = db.query(AuditLog).filter(AuditLog.event_type == "profile_updated").one()
    assert entry.area == "KALX Staff Directory"
    assert entry.actor_role == "staff"
    assert set(entry.details["changes"]) == {"pronouns", "phone", "dj_persona_ids"}


def test_paid_staff_can_edit_anyone(client: TestClient, db: Session, dj, editing, personas):
    _make_staff(db, "boss@example.com", "Boss", statuses=("Active", "Paid Staff"))
    with (
        patch(
            "app.common.services.staff_airtable.update_staff_record", new_callable=AsyncMock
        ),
        patch(
            "app.common.services.user_service.UserService.sync_one", new_callable=AsyncMock
        ),
    ):
        response = client.patch(
            f"/api/directory/{dj.id}/profile",
            json={**_UPDATE, "dj_persona_ids": [111]},
            headers=_as("boss@example.com"),
        )
    assert response.status_code == 200
    assert response.json()["can_edit"] is True
    entry = db.query(AuditLog).filter(AuditLog.event_type == "profile_updated").one()
    assert entry.actor_email == "boss@example.com"
    assert entry.actor_role == "paid_staff"


def test_other_site_admins_can_see_but_not_edit(
    client: TestClient, db: Session, dj, editing, monkeypatch
):
    monkeypatch.setattr(config.settings, "site_admin_emails", "admin@example.com")
    _make_staff(db, "admin@example.com", "Admin")
    headers = _as("admin@example.com")
    response = client.get(f"/api/directory/{dj.id}/profile", headers=headers)
    assert response.status_code == 200
    assert response.json()["can_edit"] is False
    response = client.patch(
        f"/api/directory/{dj.id}/profile", json=_UPDATE, headers=headers
    )
    assert response.status_code == 403
    response = client.post(
        f"/api/directory/{dj.id}/photo",
        files={"photo": ("me.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 403


def test_other_staff_cant_edit(client: TestClient, db: Session, dj, editing):
    _make_staff(db, "amy@example.com", "Amy Adams")
    response = client.patch(
        f"/api/directory/{dj.id}/profile", json=_UPDATE, headers=_as("amy@example.com")
    )
    assert response.status_code == 403


def test_saving_nothing_changed_doesnt_write(client: TestClient, db: Session, dj, editing):
    with patch(
        "app.common.services.staff_airtable.update_staff_record", new_callable=AsyncMock
    ) as update:
        response = client.patch(
            f"/api/directory/{dj.id}/profile",
            json={
                "first_name": "Zed",
                "surname": "Zulu",
                "pronouns": "he/him",
                "phone": "510-555-0100",
                "dj_persona_ids": [111],
            },
            headers=_as("dj@example.com"),
        )
    assert response.status_code == 200
    update.assert_not_awaited()


@pytest.mark.parametrize(
    "change,status,detail",
    [
        ({"first_name": "  "}, 422, "First name is required"),
        ({"phone": "555-0100"}, 422, "Phone must be a 10-digit US number"),
        ({"pronouns": "x" * 41}, 422, None),
        ({"dj_persona_ids": [176287]}, 400, "These aren't DJ names in Spinitron: 176287"),
    ],
)
def test_invalid_profile_values(
    client: TestClient, db: Session, dj, editing, personas, change, status, detail
):
    response = client.patch(
        f"/api/directory/{dj.id}/profile",
        json={**_UPDATE, **change},
        headers=_as("dj@example.com"),
    )
    assert response.status_code == status
    if detail:
        assert response.json()["detail"] == detail


def test_a_blank_phone_clears_it(client: TestClient, db: Session, dj, editing):
    with (
        patch(
            "app.common.services.staff_airtable.update_staff_record", new_callable=AsyncMock
        ) as update,
        patch(
            "app.common.services.user_service.UserService.sync_one", new_callable=AsyncMock
        ),
    ):
        client.patch(
            f"/api/directory/{dj.id}/profile",
            json={**_UPDATE, "pronouns": "he/him", "phone": "", "dj_persona_ids": [111]},
            headers=_as("dj@example.com"),
        )
    update.assert_awaited_once_with(DJ_ID, {"Phone": None})


def test_dj_name_markdown_escapes_brackets():
    assert (
        profile_service.dj_name_markdown([(5, "DJ [Live]")])
        == "[DJ \\[Live\\]](https://spinitron.com/KALX/dj/5/)"
    )


# --- Photo ---


def _jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_photo_upload_is_off_by_default(client: TestClient, db: Session, dj):
    response = client.post(
        f"/api/directory/{dj.id}/photo",
        files={"photo": ("me.jpg", _jpeg(), "image/jpeg")},
        headers=_as("dj@example.com"),
    )
    assert response.status_code == 403


def test_photo_upload(client: TestClient, db: Session, dj, editing):
    with (
        patch(
            "app.common.services.staff_airtable.replace_staff_photo", new_callable=AsyncMock
        ) as replace,
        patch(
            "app.common.services.user_service.UserService.sync_one", new_callable=AsyncMock
        ),
    ):
        response = client.post(
            f"/api/directory/{dj.id}/photo",
            files={"photo": ("me.jpg", _jpeg(), "image/jpeg")},
            headers=_as("dj@example.com"),
        )
    assert response.status_code == 200
    assert replace.await_args.args[:3] == (DJ_ID, "me.jpg", "image/jpeg")
    assert (
        db.query(AuditLog).filter(AuditLog.event_type == "profile_photo_updated").count()
        == 1
    )


@pytest.mark.parametrize(
    "content,content_type,status",
    [
        (b"GIF89a....", "image/gif", 422),
        (b"not really a jpeg", "image/jpeg", 422),
        (b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024), "image/jpeg", 413),
    ],
)
def test_photo_upload_limits(
    client: TestClient, db: Session, dj, editing, content, content_type, status
):
    response = client.post(
        f"/api/directory/{dj.id}/photo",
        files={"photo": ("me", content, content_type)},
        headers=_as("dj@example.com"),
    )
    assert response.status_code == status


# --- Personas ---


def test_persona_search_leaves_out_placeholders(
    client: TestClient, db: Session, dj, personas
):
    response = client.get("/api/directory/personas?q=dj", headers=_as("dj@example.com"))
    assert response.json() == [{"id": 111, "name": "DJ Zed"}]


def test_resolving_a_persona_link(client: TestClient, db: Session, dj, personas):
    response = client.post(
        "/api/directory/personas/resolve",
        json={"url": "https://widgets.spinitron.com/KALX/dj/222/Zed-Esq"},
        headers=_as("dj@example.com"),
    )
    assert response.json() == {"id": 222, "name": "Zed, Esq."}


def test_resolving_a_playlist_link(client: TestClient, db: Session, dj, personas):
    with patch(
        "app.directory.services.profile.SpinitronService.fetch_playlist",
        new_callable=AsyncMock,
        return_value={"id": 22868763, "persona_id": 111},
    ) as fetch:
        response = client.post(
            "/api/directory/personas/resolve",
            json={"url": "https://spinitron.com/m/playlist/view/22868763"},
            headers=_as("dj@example.com"),
        )
    fetch.assert_awaited_once_with(22868763)
    assert response.json() == {"id": 111, "name": "DJ Zed"}


@pytest.mark.parametrize(
    "playlist",
    [None, {"id": 1}, {"id": 1, "persona_id": 176287}, {"id": 1, "persona_id": 999}],
)
def test_resolving_a_bad_playlist_link(
    client: TestClient, db: Session, dj, personas, playlist
):
    with patch(
        "app.directory.services.profile.SpinitronService.fetch_playlist",
        new_callable=AsyncMock,
        return_value=playlist,
    ):
        response = client.post(
            "/api/directory/personas/resolve",
            json={"url": "https://spinitron.com/m/playlist/view/1"},
            headers=_as("dj@example.com"),
        )
    assert response.status_code == 400


def test_resolving_a_playlist_link_when_spinitron_fails(
    client: TestClient, db: Session, dj, personas
):
    with patch(
        "app.directory.services.profile.SpinitronService.fetch_playlist",
        new_callable=AsyncMock,
        side_effect=RuntimeError("down"),
    ):
        response = client.post(
            "/api/directory/personas/resolve",
            json={"url": "https://spinitron.com/m/playlist/view/1"},
            headers=_as("dj@example.com"),
        )
    assert response.status_code == 502


@pytest.mark.parametrize(
    "url",
    [
        "https://spinitron.com/KALX/dj/176287/",
        "https://spinitron.com/KALX/dj/999/",
        "https://example.com/KALX/dj/111/",
        "https://spinitron.com/m/playlist/edit/22868763",
    ],
)
def test_resolving_a_bad_persona_link(client: TestClient, db: Session, dj, personas, url):
    response = client.post(
        "/api/directory/personas/resolve", json={"url": url}, headers=_as("dj@example.com")
    )
    assert response.status_code == 400


# --- DJ Quiz deadlines ---


def test_only_site_admins_manage_quiz_deadlines(client: TestClient, db: Session, dj):
    assert (
        client.get(
            "/api/directory/admin/dj-quiz-deadlines", headers=_as("dj@example.com")
        ).status_code
        == 403
    )


def test_quiz_deadlines(client: TestClient, db: Session):
    _make_staff(db, "boss@example.com", "Boss", statuses=("Active", "Paid Staff"))
    h = _as("boss@example.com")
    assert (
        client.put(
            "/api/directory/admin/dj-quiz-deadlines/2027",
            json={"deadline": "2027-09-30"},
            headers=h,
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/directory/admin/dj-quiz-deadlines/2026",
            json={"deadline": "2026-09-30"},
            headers=h,
        ).status_code
        == 200
    )
    wrong_year = client.put(
        "/api/directory/admin/dj-quiz-deadlines/2028",
        json={"deadline": "2027-09-30"},
        headers=h,
    )
    assert wrong_year.status_code == 422
    listed = client.get("/api/directory/admin/dj-quiz-deadlines", headers=h).json()
    assert listed == [
        {"year": 2027, "deadline": "2027-09-30"},
        {"year": 2026, "deadline": "2026-09-30"},
    ]
    assert (
        client.delete("/api/directory/admin/dj-quiz-deadlines/2027", headers=h).status_code
        == 204
    )
    events = [e.event_type for e in db.query(AuditLog).order_by(AuditLog.id)]
    assert events == [
        "dj_quiz_deadline_set",
        "dj_quiz_deadline_set",
        "dj_quiz_deadline_removed",
    ]
