"""Tests for deploy_common.py and notify.py: settings, GitHub and email."""

import io
import json
import urllib.error
from pathlib import Path

import pytest

import deploy_common
import notify
from conftest import write_env
from deploy_common import get_environment, read_env_file


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send_message(self, message):
        FakeSMTP.sent.append((self.host, self.port, message))


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> list:
    FakeSMTP.sent = []
    monkeypatch.setattr(deploy_common.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP.sent


def test_read_env_file(home):
    path = write_env(
        home,
        "staging",
        "# comment\nwebmaster_email='web@example.com'\n\nAPP_VERSION=\"v1\"\nBAD\n",
    )
    assert read_env_file(path) == {
        "WEBMASTER_EMAIL": "web@example.com",
        "APP_VERSION": "v1",
    }
    assert read_env_file(home / "missing") == {}


def test_send_email_uses_the_local_relay(home, smtp):
    write_env(
        home, "production", "WEBMASTER_EMAIL=web@example.com\nLOCAL_SMTP_HOST=relay\n"
    )
    assert deploy_common.send_email(get_environment("production"), "Subject", "Body")
    host, port, message = smtp[0]
    assert (host, port) == ("relay", 25)
    assert message["To"] == "web@example.com"
    assert message["From"] == "noreply@kalx.berkeley.edu"


def test_send_email_without_a_recipient_sends_nothing(home, smtp):
    write_env(home, "production", "")
    assert not deploy_common.send_email(get_environment("production"), "Subject", "Body")
    assert smtp == []


def test_the_same_failure_is_emailed_once_in_12_hours(home, smtp, monkeypatch):
    write_env(home, "staging", "WEBMASTER_EMAIL=web@example.com\n")
    staging = get_environment("staging")
    assert deploy_common.send_failure_email(staging, "broken", "log")
    assert not deploy_common.send_failure_email(staging, "broken", "log")
    assert deploy_common.send_failure_email(staging, "differently broken", "log")
    assert len(smtp) == 2


def test_notify_quotes_the_saved_reason(home, smtp, monkeypatch):
    write_env(home, "production", "WEBMASTER_EMAIL=web@example.com\n")
    deploy_common.write_state(get_environment("production"), "last-failure", "It broke.")

    class Journal:
        stdout = "the log lines"
        stderr = ""

    monkeypatch.setattr(notify.subprocess, "run", lambda *a, **k: Journal())
    assert notify.main(["failure", "production"]) == 0
    message = smtp[0][2]
    assert message["Subject"] == "[KALX Staff App] The production deploy failed"
    body = message.get_content()
    assert "It broke." in body and "the log lines" in body


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_github_json_retries_without_a_rejected_token(home, smtp, monkeypatch):
    write_env(home, "staging", "WEBMASTER_EMAIL=web@example.com\n")
    token = home / ".config" / "staff-app-deploy" / "github-token"
    token.parent.mkdir(parents=True)
    token.write_text("expired\n")
    sent_tokens = []

    def urlopen(request, timeout=None):
        sent_tokens.append(request.get_header("Authorization"))
        if request.get_header("Authorization"):
            raise urllib.error.HTTPError(request.full_url, 401, "Bad credentials", {}, None)
        return FakeResponse(json.dumps({"tag_name": "v1"}).encode())

    monkeypatch.setattr(deploy_common.urllib.request, "urlopen", urlopen)
    staging = get_environment("staging")
    assert deploy_common.github_json(staging, "/x") == {"tag_name": "v1"}
    assert deploy_common.github_json(staging, "/x") == {"tag_name": "v1"}
    assert sent_tokens == ["Bearer expired", None, "Bearer expired", None]
    assert len(smtp) == 1  # the token warning, once a day
    assert "token needs replacing" in smtp[0][2]["Subject"]


def test_github_json_reports_an_outage(home, monkeypatch):
    def urlopen(request, timeout=None):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(deploy_common.urllib.request, "urlopen", urlopen)
    with pytest.raises(deploy_common.GitHubUnavailable):
        deploy_common.github_json(get_environment("staging"), "/x")


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/kalx-berkeley/staff-app.git",
        "https://github.com/kalx-berkeley/staff-app",
        "git@github.com:kalx-berkeley/staff-app.git",
    ],
)
def test_repo_slug(url, monkeypatch):
    class Result:
        stdout = url + "\n"

    monkeypatch.setattr(deploy_common, "run", lambda *a, **k: Result())
    assert deploy_common.repo_slug() == "kalx-berkeley/staff-app"


def test_write_atomically_keeps_the_mode(tmp_path: Path):
    path = tmp_path / "file"
    path.write_text("old")
    path.chmod(0o600)
    deploy_common.write_atomically(path, "new")
    assert path.read_text() == "new" and path.stat().st_mode & 0o777 == 0o600


def test_notify_still_emails_when_the_log_cant_be_read(home, smtp, monkeypatch):
    write_env(home, "staging", "WEBMASTER_EMAIL=web@example.com\n")

    def no_journalctl(*args, **kwargs):
        raise FileNotFoundError("journalctl")

    monkeypatch.setattr(notify.subprocess, "run", no_journalctl)
    assert notify.main(["failure", "staging"]) == 0
    assert "couldn't be read" in smtp[0][2].get_content()
