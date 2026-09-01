"""Tests for the email notification service."""

import logging
from unittest.mock import patch, MagicMock


def test_send_email_staging_logs_not_sends(caplog):
    """In staging mode, send_email suppresses delivery and logs instead."""
    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.environment = "staging"
        mock_settings.smtp2go_api_key = "fake-key"
        mock_settings.smtp2go_from_email = "noreply@kalx.berkeley.edu"
        mock_settings.webmaster_email = None

        with caplog.at_level(logging.INFO, logger="app.services.notification_service"):
            from app.services.notification_service import send_email

            send_email("user@example.com", "Test Subject", "Test body")

    assert any("suppressed" in r.message for r in caplog.records)
    assert any("user@example.com" in r.message for r in caplog.records)


def test_send_email_no_api_key_uses_local_smtp():
    """When smtp2go_api_key is None, send_email delivers via local SMTP."""
    mock_smtp_instance = MagicMock()
    mock_smtp_cls = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.services.notification_service.settings") as mock_settings,
        patch("app.services.notification_service.smtplib.SMTP", mock_smtp_cls),
    ):
        mock_settings.environment = "production"
        mock_settings.smtp2go_api_key = None
        mock_settings.smtp2go_from_email = "noreply@kalx.berkeley.edu"
        mock_settings.webmaster_email = None
        mock_settings.local_smtp_host = "localhost"
        mock_settings.local_smtp_port = 25

        from app.services.notification_service import send_email

        send_email("user@example.com", "Test Subject", "Test body")

    mock_smtp_cls.assert_called_once_with("localhost", 25)
    mock_smtp_instance.sendmail.assert_called_once()


def test_send_email_production_calls_smtp2go():
    """In production with an API key, send_email calls smtp2go."""
    mock_client = MagicMock()
    mock_client.send.return_value = MagicMock(success=True)

    with (
        patch("app.services.notification_service.settings") as mock_settings,
        patch("app.services.notification_service.Smtp2goClient", return_value=mock_client),
    ):
        mock_settings.environment = "production"
        mock_settings.smtp2go_api_key = "real-key"
        mock_settings.smtp2go_from_email = "noreply@kalx.berkeley.edu"

        from app.services.notification_service import send_email

        send_email("user@example.com", "Subject", "Body")

    mock_client.send.assert_called_once()
    call_kwargs = mock_client.send.call_args.kwargs
    assert call_kwargs["recipients"] == ["user@example.com"]
    assert call_kwargs["subject"] == "Subject"
