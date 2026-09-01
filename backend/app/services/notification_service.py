"""Email notification service using smtp2go or local SMTP."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

try:
    from smtp2go.core import Smtp2goClient
except ImportError:
    Smtp2goClient = None  # type: ignore[assignment,misc]


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    db: "Session | None" = None,
) -> None:
    """
    Send an email notification.

    :param to_email: Recipient email address.
    :param subject: Email subject line.
    :param body_text: Plain-text body.
    :param body_html: Optional HTML body.
    :param db: Optional database session; when provided, a successful send is audit-logged.

    Uses smtp2go when SMTP2GO_API_KEY is set; falls back to the local mail server otherwise.
    In staging mode, suppresses delivery to non-webmaster recipients.
    """
    is_webmaster = settings.webmaster_email and to_email == settings.webmaster_email
    if settings.environment == "staging" and not is_webmaster:
        preview = body_text[:200].replace("\n", " ")
        logger.info(
            "Email suppressed (staging) — to=%s subject=%r body_preview=%r",
            to_email,
            subject,
            preview,
        )
        _audit_email(db, to_email, subject, body_text, body_html, sent=False)
        return

    if settings.smtp2go_api_key:
        _send_via_smtp2go(to_email, subject, body_text, body_html, db)
    else:
        _send_via_local_smtp(to_email, subject, body_text, body_html, db)


def _send_via_smtp2go(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None,
    db: "Session | None",
) -> None:
    if Smtp2goClient is None:
        logger.error("smtp2go package is not installed; cannot send email to %s", to_email)
        return

    client = Smtp2goClient(api_key=settings.smtp2go_api_key)
    kwargs: dict = {
        "sender": settings.smtp2go_from_email,
        "recipients": [to_email],
        "subject": subject,
        "text": body_text,
    }
    if body_html is not None:
        kwargs["html"] = body_html

    response = client.send(**kwargs)
    if not response.success:
        logger.error(
            "smtp2go send failed to=%s subject=%r: %s", to_email, subject, response
        )
    else:
        logger.info("Email sent via smtp2go to=%s subject=%r", to_email, subject)
        _audit_email(db, to_email, subject, body_text, body_html, sent=True)


def _send_via_local_smtp(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None,
    db: "Session | None",
) -> None:
    if body_html is not None:
        msg: MIMEMultipart | MIMEText = MIMEMultipart("alternative")
        assert isinstance(msg, MIMEMultipart)
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))
    else:
        msg = MIMEText(body_text, "plain")

    msg["Subject"] = subject
    msg["From"] = settings.smtp2go_from_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.local_smtp_host, settings.local_smtp_port) as smtp:
            smtp.sendmail(settings.smtp2go_from_email, [to_email], msg.as_string())
        logger.info("Email sent via local SMTP to=%s subject=%r", to_email, subject)
        _audit_email(db, to_email, subject, body_text, body_html, sent=True)
    except OSError:
        logger.exception("Local SMTP send failed to=%s subject=%r", to_email, subject)


def _audit_email(
    db: "Session | None",
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None,
    sent: bool,
) -> None:
    if db is None:
        return
    from app.services.audit_service import log_event

    details: dict = {
        "to": to_email,
        "subject": subject,
        "body_text": body_text,
        "sent": sent,
    }
    if body_html is not None:
        details["body_html"] = body_html

    log_event(
        db,
        event_type="email_sent",
        actor_role="system",
        details=details,
    )
