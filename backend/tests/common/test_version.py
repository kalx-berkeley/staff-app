"""Tests for the deployed version endpoint."""

from fastapi.testclient import TestClient

from app.config import settings

SIGNED_IN = {"X-Forwarded-User": "someone@example.com"}


def test_reports_the_deployed_version_uncached(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "app_version", "v1.2.3")

    response = client.get("/api/version", headers=SIGNED_IN)

    assert response.status_code == 200
    assert response.json() == {"version": "v1.2.3"}
    assert response.headers["Cache-Control"] == "no-store"


def test_reports_no_version_when_the_deploy_set_none(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "app_version", None)

    response = client.get("/api/version", headers=SIGNED_IN)

    assert response.json() == {"version": None}


def test_signed_out_requests_are_refused(client: TestClient):
    response = client.get("/api/version", headers={"X-Forwarded-For": "203.0.113.9"})

    assert response.status_code == 401
