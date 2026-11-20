"""Tests for telling who is on air (on_air_identity) and GET /api/dj/on-air."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_spinitron_show import SpecialtyShowSpinitronShow
from app.models.spinitron_persona import SpinitronPersona
from app.models.spinitron_playlist import SpinitronPlaylist
from app.models.spinitron_show import SpinitronShow
from app.pass_giveaway.services.on_air_identity import on_air
from app.scheduler import next_slot_resync_time

SERVICE = "app.pass_giveaway.services.on_air_identity"
DJ_STUDIO_IP = "192.168.1.100"
PLACEHOLDER = 900
NOW = datetime(2026, 11, 16, 20, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def setup(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "spinitron_placeholder_persona_ids", str(PLACEHOLDER))
    db.add_all([
        SpinitronPersona(id=1, name="DJ One"),
        SpinitronPersona(id=2, name="DJ Two"),
        SpinitronPersona(id=3, name="DJ Three"),
    ])
    db.commit()
    spins(monkeypatch, [])


def spins(monkeypatch, items: list[tuple[timedelta, int]]) -> None:
    """Recent spins, as (offset from NOW, playlist ID)."""

    async def recent_spins(db):
        return [
            {"id": i, "start": (NOW + offset).isoformat(), "playlist_id": playlist_id}
            for i, (offset, playlist_id) in enumerate(items)
        ]

    monkeypatch.setattr(f"{SERVICE}.SpinMatchService.recent_spins", recent_spins)


def playlist(db: Session, id: int, start: int, end: int, persona_id=None, **kw):
    """A cached playlist from *start* to *end* minutes after NOW."""
    db.add(
        SpinitronPlaylist(
            id=id,
            start=NOW + timedelta(minutes=start),
            end=NOW + timedelta(minutes=end),
            persona_id=persona_id,
            **kw,
        )
    )
    db.commit()


def show(db: Session, id: int, start: int, end: int, persona_id=None, **kw):
    """A cached Spinitron show from *start* to *end* minutes after NOW."""
    db.add(
        SpinitronShow(
            id=id,
            start=NOW + timedelta(minutes=start),
            end=NOW + timedelta(minutes=end),
            persona_id=persona_id,
            **kw,
        )
    )
    db.commit()


def specialty(db: Session, name: str, spinitron_show_id: int, category="music"):
    s = SpecialtyShow(name=name, category=category)
    db.add(s)
    db.flush()
    db.add(
        SpecialtyShowSpinitronShow(
            specialty_show_id=s.id, spinitron_show_id=spinitron_show_id
        )
    )
    db.commit()
    return s


def who(state) -> tuple:
    i = state.identity
    return (i.kind, i.name, i.persona_id, i.specialty_show_id) if i else None


class TestIdentityOfASlot:
    async def test_a_regular_shift_is_its_persona(self, db: Session):
        playlist(db, 10, -30, 30, persona_id=1, dj_name="Old Name")
        assert who(await on_air(db, NOW)) == ("persona", "DJ One", 1, None)

    async def test_a_placeholder_persona_is_no_one(self, db: Session):
        show(db, 20, -30, 30, persona_id=PLACEHOLDER)
        state = await on_air(db, NOW)
        assert state.current is not None
        assert state.identity is None

    async def test_a_freeform_slot_is_its_persona(self, db: Session):
        # FREEFORM is only Spinitron's title for a regular DJ's unnamed show
        show(db, 20, -30, 30, persona_id=1, title="FREEFORM")
        assert who(await on_air(db, NOW)) == ("persona", "DJ One", 1, None)
        playlist(db, 10, -30, 30, persona_id=2, title="FREEFORM")
        assert who(await on_air(db, NOW)) == ("persona", "DJ Two", 2, None)

    async def test_overnights_is_no_one(self, db: Session):
        # Its persona is the KALX Overnights placeholder
        playlist(db, 10, -30, 30, persona_id=PLACEHOLDER, title="OVERNIGHTS")
        state = await on_air(db, NOW)
        assert state.current is not None
        assert state.identity is None

    async def test_automation_is_no_one(self, db: Session):
        playlist(db, 10, -30, 30, persona_id=1, automation=True, title="Roboshow")
        state = await on_air(db, NOW)
        assert state.identity is None
        assert (state.current.automation, state.current.title) == (True, "Roboshow")

    async def test_an_automation_playlist_of_a_linked_show_is_no_one(self, db: Session):
        # A pre-recorded Talk & Info Show: the page says it's pre-recorded
        specialty(db, "Arts In Review", 555, category="talk")
        playlist(db, 10, -30, 30, persona_id=1, show_id=555, automation=True)
        state = await on_air(db, NOW)
        assert state.identity is None
        assert state.current.automation is True

    async def test_a_talk_show_is_the_show_whoever_hosts_it(self, db: Session):
        talk = specialty(db, "Morning Report", 555, category="talk")
        playlist(db, 10, -30, 30, persona_id=PLACEHOLDER, show_id=555)
        assert who(await on_air(db, NOW)) == ("talk", "Morning Report", None, talk.id)

    async def test_a_music_show_is_the_show_and_its_dj(self, db: Session):
        music = specialty(db, "Take Five", 556)
        show(db, 556, -30, 30, persona_id=2)
        state = await on_air(db, NOW)
        assert who(state) == ("music", "Take Five", 2, music.id)
        assert state.identity.persona_name == "DJ Two"

    async def test_a_gap_is_no_one(self, db: Session):
        show(db, 20, 30, 90, persona_id=1)
        state = await on_air(db, NOW)
        assert state.current is None
        assert state.next.identity.persona_id == 1

    async def test_a_playlist_beats_the_show_for_the_same_slot(self, db: Session):
        show(db, 20, -30, 30, persona_id=PLACEHOLDER)
        playlist(db, 10, -30, 30, persona_id=1)
        assert who(await on_air(db, NOW))[2] == 1


class TestSpins:
    async def test_the_playlist_with_the_latest_spin_wins(self, db: Session, monkeypatch):
        playlist(db, 10, -30, 30, persona_id=1)
        playlist(db, 11, -20, 30, persona_id=2)
        spins(monkeypatch, [(timedelta(minutes=-2), 10), (timedelta(minutes=-5), 11)])
        state = await on_air(db, NOW)
        assert who(state)[2] == 1
        assert state.from_spins

    async def test_a_dj_running_over_keeps_it_until_the_next_dj_logs_a_track(
        self, db: Session, monkeypatch
    ):
        playlist(db, 10, -60, -5, persona_id=1)
        playlist(db, 11, -5, 55, persona_id=2)
        spins(monkeypatch, [(timedelta(minutes=-1), 10)])
        assert who(await on_air(db, NOW))[2] == 1
        spins(monkeypatch, [(timedelta(minutes=-1), 10), (timedelta(seconds=-10), 11)])
        assert who(await on_air(db, NOW))[2] == 2

    async def test_a_dj_who_stopped_on_time_hands_over_at_the_changeover(
        self, db: Session, monkeypatch
    ):
        playlist(db, 10, -60, -5, persona_id=1)
        playlist(db, 11, -5, 55, persona_id=2)
        spins(monkeypatch, [(timedelta(minutes=-8), 10)])
        assert who(await on_air(db, NOW))[2] == 2

    async def test_running_over_ends_after_15_minutes(self, db: Session, monkeypatch):
        playlist(db, 10, -80, -20, persona_id=1)
        playlist(db, 11, -20, 40, persona_id=2)
        spins(monkeypatch, [(timedelta(minutes=-1), 10)])
        assert who(await on_air(db, NOW))[2] == 2

    async def test_a_dj_who_starts_early_takes_over(self, db: Session, monkeypatch):
        playlist(db, 10, -55, 5, persona_id=1)
        playlist(db, 11, 5, 65, persona_id=2)
        playlist(db, 12, 65, 125, persona_id=3)
        spins(monkeypatch, [(timedelta(minutes=-1), 11)])
        state = await on_air(db, NOW)
        assert who(state)[2] == 2
        assert state.next.identity.persona_id == 3

    async def test_a_spin_in_an_unknown_playlist_fetches_it(self, db: Session, monkeypatch):
        show(db, 20, -30, 30, persona_id=PLACEHOLDER)
        spins(monkeypatch, [(timedelta(minutes=-1), 77)])
        fetched = []

        async def fetch_playlist(playlist_id):
            fetched.append(playlist_id)
            return {
                "id": playlist_id,
                "start": (NOW - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S%z"),
                "end": (NOW + timedelta(minutes=50)).strftime("%Y-%m-%dT%H:%M:%S%z"),
                "persona_id": 3,
                "show_id": 20,
            }

        monkeypatch.setattr(f"{SERVICE}.SpinitronService.fetch_playlist", fetch_playlist)
        assert who(await on_air(db, NOW))[2] == 3
        assert db.get(SpinitronPlaylist, 77).persona_id == 3
        # Cached now, so not fetched again
        await on_air(db, NOW)
        assert fetched == [77]

    async def test_without_spins_the_schedule_decides(self, db: Session, monkeypatch):
        async def broken(db):
            raise RuntimeError("Spinitron is down")

        monkeypatch.setattr(f"{SERVICE}.SpinMatchService.recent_spins", broken)
        playlist(db, 10, -30, 30, persona_id=1)
        state = await on_air(db, NOW)
        assert who(state)[2] == 1
        assert not state.from_spins


class TestEarlySwitch:
    async def test_offered_in_the_last_10_minutes(self, db: Session):
        playlist(db, 10, -55, 5, persona_id=1)
        playlist(db, 11, 5, 65, persona_id=2)
        state = await on_air(db, NOW)
        assert state.can_switch_early(NOW)
        assert not state.can_switch_early(NOW - timedelta(minutes=10))

    async def test_credit_goes_to_the_next_slot_only_when_asked_for_it(self, db: Session):
        playlist(db, 10, -55, 5, persona_id=1)
        playlist(db, 11, 5, 65, persona_id=2)
        state = await on_air(db, NOW)
        next_start = NOW + timedelta(minutes=5)
        assert state.credited(next_start, NOW).persona_id == 2
        assert state.credited(None, NOW).persona_id == 1
        # Not the next slot's start: ignored
        assert state.credited(next_start + timedelta(hours=1), NOW).persona_id == 1

    async def test_not_offered_when_the_next_slot_is_no_one(self, db: Session):
        playlist(db, 10, -55, 5, persona_id=1)
        show(db, 20, 5, 65, persona_id=PLACEHOLDER)
        state = await on_air(db, NOW)
        assert not state.can_switch_early(NOW)
        assert state.credited(NOW + timedelta(minutes=5), NOW).persona_id == 1

    async def test_not_offered_when_the_same_identity_continues(self, db: Session):
        playlist(db, 10, -55, 5, persona_id=1)
        playlist(db, 11, 5, 65, persona_id=1)
        assert not (await on_air(db, NOW)).can_switch_early(NOW)


class TestEndpoint:
    def test_returns_the_identities(self, client: TestClient, db: Session):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        talk = specialty(db, "Morning Report", 555, category="talk")
        db.add_all([
            SpinitronPlaylist(
                id=10,
                start=now - timedelta(minutes=55),
                end=now + timedelta(minutes=5),
                persona_id=1,
                dj_name="DJ One",
            ),
            SpinitronShow(
                id=555,
                start=now + timedelta(minutes=5),
                end=now + timedelta(minutes=65),
                persona_id=PLACEHOLDER,
            ),
        ])
        db.commit()
        data = client.get(
            "/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP}
        ).json()
        assert data["current"] == {
            "kind": "persona",
            "name": "DJ One",
            "persona_id": 1,
            "persona_name": "DJ One",
            "specialty_show_id": None,
        }
        assert data["next"]["kind"] == "talk"
        assert data["next"]["specialty_show_id"] == talk.id
        assert data["next_starts_at"] is not None
        assert data["can_switch_early"] is True
        assert data["current_automation"] is False

    def test_says_when_the_slot_is_pre_recorded(self, client: TestClient, db: Session):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        db.add(
            SpinitronPlaylist(
                id=10,
                start=now - timedelta(minutes=5),
                end=now + timedelta(minutes=25),
                persona_id=1,
                title="Arts In Review",
                automation=True,
            )
        )
        db.commit()
        data = client.get(
            "/api/dj/on-air", headers={"X-Forwarded-For": DJ_STUDIO_IP}
        ).json()
        assert data["current"] is None
        assert data["current_automation"] is True
        assert data["current_title"] == "Arts In Review"


class TestSlotResync:
    def test_runs_10_minutes_before_the_next_slot(self, db: Session):
        playlist(db, 10, -30, 30, persona_id=1)
        show(db, 20, 30, 90, persona_id=2)
        assert next_slot_resync_time(db, NOW) == NOW + timedelta(minutes=20)

    def test_skips_slots_starting_within_10_minutes(self, db: Session):
        playlist(db, 10, 5, 65, persona_id=1)
        playlist(db, 11, 65, 125, persona_id=2)
        assert next_slot_resync_time(db, NOW) == NOW + timedelta(minutes=55)

    def test_none_when_nothing_is_cached(self, db: Session):
        assert next_slot_resync_time(db, NOW) is None
