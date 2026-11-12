"""Tests for the email notification service."""

import email
import logging
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import Session

from app.common.areas import COMMON_AREA
from app.models.audit_log import AuditLog


def _last_audit_entry(db: Session) -> AuditLog:
    return (
        db.query(AuditLog)
        .filter(AuditLog.event_type == "email_sent")
        .order_by(AuditLog.id.desc())
        .first()
    )


def test_send_email_staging_logs_not_sends(caplog):
    """In staging mode, send_email suppresses delivery and logs instead."""
    with patch("app.common.services.notification_service.settings") as mock_settings:
        mock_settings.environment = "staging"
        mock_settings.email_from_address = "noreply@kalx.berkeley.edu"
        mock_settings.webmaster_email = None

        with caplog.at_level(
            logging.INFO, logger="app.common.services.notification_service"
        ):
            from app.common.services.notification_service import send_email

            send_email("user@example.com", "Test Subject", "Test body", area=COMMON_AREA)

    assert any("suppressed" in r.message for r in caplog.records)
    assert any("user@example.com" in r.message for r in caplog.records)
    assert any("[STAGING] Test Subject" in r.message for r in caplog.records)


def _mock_smtp():
    mock_smtp_instance = MagicMock()
    mock_smtp_cls = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)
    return mock_smtp_cls, mock_smtp_instance


def test_send_email_staging_tags_subject_and_body_for_webmaster():
    """In staging, even a delivered (webmaster) email gets a [STAGING] subject and body notice."""
    mock_smtp_cls, mock_smtp_instance = _mock_smtp()

    with (
        patch("app.common.services.notification_service.settings") as mock_settings,
        patch("app.common.services.notification_service.smtplib.SMTP", mock_smtp_cls),
    ):
        mock_settings.environment = "staging"
        mock_settings.email_from_address = "noreply@kalx.berkeley.edu"
        mock_settings.webmaster_email = "webmaster@kalx.berkeley.edu"
        mock_settings.local_smtp_host = "localhost"
        mock_settings.local_smtp_port = 25

        from app.common.services.notification_service import send_email

        send_email(
            "webmaster@kalx.berkeley.edu",
            "Test Subject",
            "Test body",
            body_html="<p>Test body</p>",
            area=COMMON_AREA,
        )

    _from, recipients, raw = mock_smtp_instance.sendmail.call_args.args
    assert recipients == ["webmaster@kalx.berkeley.edu"]
    message = email.message_from_string(raw)
    assert message["Subject"] == "[STAGING] Test Subject"
    text_part, html_part = message.get_payload()
    text = text_part.get_payload(decode=True).decode()
    html = html_part.get_payload(decode=True).decode()
    assert "Test body" in text
    assert "STAGING environment email" in text
    assert "STAGING environment email" in html


def test_send_email_uses_local_smtp():
    """In production, send_email delivers via local SMTP."""
    mock_smtp_instance = MagicMock()
    mock_smtp_cls = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.common.services.notification_service.settings") as mock_settings,
        patch("app.common.services.notification_service.smtplib.SMTP", mock_smtp_cls),
    ):
        mock_settings.environment = "production"
        mock_settings.email_from_address = "noreply@kalx.berkeley.edu"
        mock_settings.webmaster_email = None
        mock_settings.local_smtp_host = "localhost"
        mock_settings.local_smtp_port = 25

        from app.common.services.notification_service import send_email

        send_email("user@example.com", "Test Subject", "Test body", area=COMMON_AREA)

    mock_smtp_cls.assert_called_once_with("localhost", 25)
    mock_smtp_instance.sendmail.assert_called_once()


def test_send_email_local_smtp_success_audits_response_details(db: Session):
    """A successful local SMTP send records the host/port used on the audit row."""
    mock_smtp_instance = MagicMock()
    mock_smtp_cls = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)
    mock_smtp_instance.sendmail.return_value = {}

    with (
        patch("app.common.services.notification_service.settings") as mock_settings,
        patch("app.common.services.notification_service.smtplib.SMTP", mock_smtp_cls),
    ):
        mock_settings.environment = "production"
        mock_settings.email_from_address = "noreply@kalx.berkeley.edu"
        mock_settings.webmaster_email = None
        mock_settings.local_smtp_host = "localhost"
        mock_settings.local_smtp_port = 25

        from app.common.services.notification_service import send_email

        send_email("user@example.com", "Test Subject", "Test body", db=db, area=COMMON_AREA)

    entry = _last_audit_entry(db)
    assert entry is not None
    assert entry.details["sent"] is True
    assert entry.details["response"] == {
        "smtp_host": "localhost",
        "smtp_port": 25,
        "refused_recipients": None,
    }


def test_send_email_local_smtp_failure_is_audited(db: Session):
    """A local SMTP OSError still writes an audit row, with the error message attached."""
    mock_smtp_cls = MagicMock(side_effect=OSError("Connection refused"))

    with (
        patch("app.common.services.notification_service.settings") as mock_settings,
        patch("app.common.services.notification_service.smtplib.SMTP", mock_smtp_cls),
    ):
        mock_settings.environment = "production"
        mock_settings.email_from_address = "noreply@kalx.berkeley.edu"
        mock_settings.webmaster_email = None
        mock_settings.local_smtp_host = "localhost"
        mock_settings.local_smtp_port = 25

        from app.common.services.notification_service import send_email

        send_email("user@example.com", "Test Subject", "Test body", db=db, area=COMMON_AREA)

    entry = _last_audit_entry(db)
    assert entry is not None
    assert entry.details["sent"] is False
    assert entry.details["response"] == {
        "smtp_host": "localhost",
        "smtp_port": 25,
        "error": "Connection refused",
    }


def test_send_email_staging_suppressed_is_audited_with_reason(db: Session):
    """Staging suppression writes an audit row explaining why nothing was sent."""
    with patch("app.common.services.notification_service.settings") as mock_settings:
        mock_settings.environment = "staging"
        mock_settings.email_from_address = "noreply@kalx.berkeley.edu"
        mock_settings.webmaster_email = None

        from app.common.services.notification_service import send_email

        send_email("user@example.com", "Test Subject", "Test body", db=db, area=COMMON_AREA)

    entry = _last_audit_entry(db)
    assert entry is not None
    assert entry.details["sent"] is False
    assert entry.details["response"] == {"reason": "staging_suppressed"}
