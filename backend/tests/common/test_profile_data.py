"""Tests for the data behind the Staff Directory's profile page: the Airtable
staff sync's new fields, re-syncing one record, writing to Airtable, and
copying Spinitron playlists."""

import asyncio
import json
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx2 as httpx
import pytest
from sqlalchemy.orm import Session

from app import config
from app.common.services import spinitron_service, staff_airtable
from app.common.services.spinitron_service import SpinitronService
from app.common.services.user_service import UserService
from app.directory.services import shift_sync
from app.models.dj_shift_playlist import DjShiftPlaylist
from app.models.job_log import JobLog
from app.models.staff import Staff


@pytest.fixture
def airtable_config(monkeypatch):
    monkeypatch.setattr(config.settings, "airtable_api_key", "key")
    monkeypatch.setattr(config.settings, "airtable_base_id", "appBASE")


def _mock_client(monkeypatch, module, handler):
    """Make *module*'s httpx.AsyncClient send requests to *handler*."""
    real = httpx.AsyncClient
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: real(transport=httpx.MockTransport(handler)),
    )


_FIELDS = {
    "Email address": "dj@example.com",
    "First Name": "Zed",
    "Surname": "Zulu",
    "Status": ["Active", "Sublist DJ"],
    "DJ Quiz": ["2026", "2025", "not a year"],
}


def test_sync_stores_first_name_surname_and_dj_quiz_years(db: Session):
    with patch(
        "app.common.services.user_service.UserService.fetch_airtable_records",
        new_callable=AsyncMock,
        return_value=[{"id": "recDJ", "fields": _FIELDS}],
    ):
        result = asyncio.run(UserService.sync_from_airtable(db))
    assert result["errors"] == []
    staff = db.query(Staff).one()
    assert (staff.name, staff.first_name, staff.surname) == ("Zed Zulu", "Zed", "Zulu")
    assert staff.dj_quiz_years == [2025, 2026]


def test_sync_one_updates_one_staff_member(db: Session):
    staff = Staff(email="dj@example.com", name="Old", phone="", airtable_record_id="recDJ")
    db.add(staff)
    db.commit()
    fields = {**_FIELDS, "Pronouns": "they/them", "Phone": "(510) 555-0199"}
    with patch(
        "app.common.services.staff_airtable.get_staff_record",
        new_callable=AsyncMock,
        return_value={"id": "recDJ", "fields": fields},
    ):
        result = asyncio.run(UserService.sync_one(db, "recDJ"))
    assert result["staff_upserted"] == ["dj@example.com"]
    db.refresh(staff)
    assert staff.name == "Zed Zulu"
    assert staff.pronouns == "they/them"
    assert staff.phone == "(510) 555-0199"
    assert sorted(s.status for s in staff.statuses) == ["Active", "Sublist DJ"]


def test_update_staff_record_patches_the_record(monkeypatch, airtable_config):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "recDJ", "fields": {}})

    _mock_client(monkeypatch, staff_airtable, handler)
    asyncio.run(staff_airtable.update_staff_record("recDJ", {"Pronouns": "she/her"}))
    assert requests[0].method == "PATCH"
    assert str(requests[0].url).endswith("/appBASE/Online%20Staff%20App%20Directory/recDJ")
    assert json.loads(requests[0].content) == {"fields": {"Pronouns": "she/her"}}


def test_airtable_errors_become_502s(monkeypatch, airtable_config):
    from fastapi import HTTPException

    _mock_client(
        monkeypatch,
        staff_airtable,
        lambda request: httpx.Response(
            403, json={"error": {"type": "INVALID_PERMISSIONS", "message": "Read only"}}
        ),
    )
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(staff_airtable.update_staff_record("recDJ", {"Pronouns": "x"}))
    assert excinfo.value.status_code == 502
    assert excinfo.value.detail == "Airtable couldn't save the staff record: Read only"


def test_replacing_a_photo_uploads_it_then_keeps_only_it(monkeypatch, airtable_config):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.host == "content.airtable.com":
            return httpx.Response(
                200,
                json={
                    "id": "recDJ",
                    "fields": {"fldPHOTO": [{"id": "attOLD"}, {"id": "attNEW"}]},
                },
            )
        return httpx.Response(200, json={"id": "recDJ", "fields": {}})

    _mock_client(monkeypatch, staff_airtable, handler)
    asyncio.run(
        staff_airtable.replace_staff_photo("recDJ", "me.jpg", "image/jpeg", b"\xff\xd8\xff")
    )
    upload, keep = requests
    assert (
        str(upload.url)
        == "https://content.airtable.com/v0/appBASE/recDJ/Photo/uploadAttachment"
    )
    body = json.loads(upload.content)
    assert body["contentType"] == "image/jpeg"
    assert body["filename"] == "me.jpg"
    assert json.loads(keep.content) == {"fields": {"Photo": [{"id": "attNEW"}]}}


def test_playlists_carry_their_show_and_automation(monkeypatch):
    monkeypatch.setattr(config.settings, "spinitron_api_key", "key")
    _mock_client(
        monkeypatch,
        spinitron_service,
        lambda request: httpx.Response(
            200,
            json={
                "items": [{
                    "id": 23200419,
                    "persona_id": 111,
                    "show_id": 301137,
                    "start": "2026-10-19T02:00:00+0000",
                    "end": "2026-10-19T04:00:00+0000",
                    "title": "FREEFORM",
                    "automation": 1,
                }],
                "_meta": {"pageCount": 1},
            },
        ),
    )
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    [playlist] = asyncio.run(SpinitronService.fetch_playlists(start, start))
    assert playlist["show_id"] == 301137
    assert playlist["automation"] is True


def test_shift_sync_replaces_the_stored_playlists(db: Session, monkeypatch):
    monkeypatch.setattr(config.settings, "spinitron_api_key", "key")
    db.add(
        DjShiftPlaylist(
            id=1,
            persona_id=1,
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 2, tzinfo=timezone.utc),
        )
    )
    db.commit()
    item = {
        "id": 2,
        "persona_id": 111,
        "show_id": 5,
        "start": datetime(2026, 9, 1, 17, tzinfo=timezone.utc),
        "end": datetime(2026, 9, 1, 19, tzinfo=timezone.utc),
        "title": "Night Moves",
        "automation": False,
    }
    with patch(
        "app.common.services.spinitron_service.SpinitronService.fetch_playlists",
        new_callable=AsyncMock,
        return_value=[item, item],
    ) as fetch:
        count = asyncio.run(shift_sync.sync_shift_playlists(db, trigger="manual"))
    assert count == 1
    assert [p.id for p in db.query(DjShiftPlaylist)] == [2]
    assert db.query(JobLog).filter(JobLog.job_id == "dj_shift_sync").count() == 1
    assert shift_sync.last_synced_at(db) is not None
    start = fetch.await_args.args[0]
    assert start.astimezone(shift_sync.PACIFIC).day == 1


def test_the_shift_window_starts_with_the_previous_quarter():
    start = shift_sync.window_start(date(2026, 10, 20))
    assert start == datetime(2026, 5, 1, 7, tzinfo=timezone.utc)


def test_shift_sync_needs_spinitron(db: Session, monkeypatch):
    monkeypatch.setattr(config.settings, "spinitron_api_key", None)
    assert asyncio.run(shift_sync.sync_shift_playlists(db)) is None
