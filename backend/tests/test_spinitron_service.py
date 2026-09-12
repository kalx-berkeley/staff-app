"""Tests for SpinitronService helpers that don't require mocking HTTP calls."""

from datetime import datetime, timedelta, timezone

from app.services.spinitron_service import SpinitronService, dedupe_by_id


class TestExtractPersonaId:
    def test_prefers_direct_persona_id_field(self):
        item = {"persona_id": 42, "_links": {"personas": [{"href": "/api/personas/99"}]}}

        assert SpinitronService._extract_persona_id(item) == 42

    def test_falls_back_to_links_personas_href(self):
        item = {"_links": {"personas": [{"href": "/api/personas/99"}]}}

        assert SpinitronService._extract_persona_id(item) == 99

    def test_returns_none_when_no_persona_present(self):
        assert SpinitronService._extract_persona_id({}) is None


def _item(id: int):
    now = datetime.now(timezone.utc)
    return {
        "id": id,
        "start": now,
        "end": now + timedelta(hours=1),
        "persona_id": None,
        "title": None,
    }


class TestDedupeById:
    def test_merges_lists_keeping_first_occurrence(self):
        first = [_item(1), _item(2)]
        second = [_item(2), _item(3)]

        merged = dedupe_by_id(first, second)

        assert [item["id"] for item in merged] == [1, 2, 3]
        # The kept copy of id=2 is the one from the first list.
        assert merged[1] is first[1]

    def test_handles_no_lists(self):
        assert dedupe_by_id() == []

    def test_handles_empty_lists(self):
        assert dedupe_by_id([], []) == []
