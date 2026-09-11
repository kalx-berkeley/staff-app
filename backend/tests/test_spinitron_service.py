"""Tests for SpinitronService helpers that don't require mocking HTTP calls."""

from app.services.spinitron_service import SpinitronService


class TestExtractPersonaId:
    def test_prefers_direct_persona_id_field(self):
        item = {"persona_id": 42, "_links": {"personas": [{"href": "/api/personas/99"}]}}

        assert SpinitronService._extract_persona_id(item) == 42

    def test_falls_back_to_links_personas_href(self):
        item = {"_links": {"personas": [{"href": "/api/personas/99"}]}}

        assert SpinitronService._extract_persona_id(item) == 99

    def test_returns_none_when_no_persona_present(self):
        assert SpinitronService._extract_persona_id({}) is None
