"""Fixtures for the common tests."""

import pytest

from app.common.services import user_service


@pytest.fixture(autouse=True)
def no_post_sync_hooks(monkeypatch):
    """Leave out the sub-sites' sync hooks: these tests' mocks of
    fetch_airtable_records return staff records for every table, which aren't
    what a hook's table holds."""
    monkeypatch.setattr(user_service, "_post_sync_hooks", [])
