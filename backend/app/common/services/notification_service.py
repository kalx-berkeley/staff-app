"""Email notification service using the local SMTP relay."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    db: "Session | None" = None,
    *,
    area: str,
) -> None:
    """
    Send an email notification.

    :param to_email: Recipient email address.
    :param subject: Email subject line.
    :param body_text: Plain-text body.
    :param body_html: Optional HTML body.
    :param db: Optional database session; when provided, every send attempt (success or
        failure) is audit-logged, including response/error details.
    :param area: The part of the app sending the email, one of `app.common.areas`,
        recorded in the audit log.

    Sends through the local mail server (LOCAL_SMTP_HOST/LOCAL_SMTP_PORT).
    In staging mode, suppresses delivery to non-webmaster recipients, and tags any email
    that is sent (or logged) with a "[STAGING]" subject prefix and an in-body notice, so
    recipients can't mistake it for a production notification.
    """
    if settings.environment == "staging":
        subject = f"[STAGING] {subject}"
        staging_notice = (
            "This is a STAGING environment email — it was not sent by the production "
            "KALX staff-app."
        )
        body_text = f"{body_text}\n\n---\n{staging_notice}\n"
        if body_html is not None:
            body_html = f"{body_html}<hr><p><strong>{staging_notice}</strong></p>"

    is_webmaster = settings.webmaster_email and to_email == settings.webmaster_email
    if settings.environment == "staging" and not is_webmaster:
        preview = body_text[:200].replace("\n", " ")
        logger.info(
            "Email suppressed (staging) — to=%s subject=%r body_preview=%r",
            to_email,
            subject,
            preview,
        )
        _audit_email(
            db,
            to_email,
            subject,
            body_text,
            body_html,
            sent=False,
            area=area,
            response_details={"reason": "staging_suppressed"},
        )
        return

    _send_via_local_smtp(to_email, subject, body_text, body_html, db, area)


def _send_via_local_smtp(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None,
    db: "Session | None",
    area: str,
) -> None:
    if body_html is not None:
        msg: MIMEMultipart | MIMEText = MIMEMultipart("alternative")
        assert isinstance(msg, MIMEMultipart)
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))
    else:
        msg = MIMEText(body_text, "plain")

    msg["Subject"] = subject
    msg["From"] = settings.email_from_address
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.local_smtp_host, settings.local_smtp_port) as smtp:
            refused = smtp.sendmail(
                settings.email_from_address, [to_email], msg.as_string()
            )
        logger.info("Email sent via local SMTP to=%s subject=%r", to_email, subject)
        _audit_email(
            db,
            to_email,
            subject,
            body_text,
            body_html,
            sent=True,
            area=area,
            response_details={
                "smtp_host": settings.local_smtp_host,
                "smtp_port": settings.local_smtp_port,
                "refused_recipients": refused or None,
            },
        )
    except OSError as exc:
        logger.exception("Local SMTP send failed to=%s subject=%r", to_email, subject)
        _audit_email(
            db,
            to_email,
            subject,
            body_text,
            body_html,
            sent=False,
            area=area,
            response_details={
                "smtp_host": settings.local_smtp_host,
                "smtp_port": settings.local_smtp_port,
                "error": str(exc),
            },
        )


def _audit_email(
    db: "Session | None",
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None,
    sent: bool,
    area: str,
    response_details: dict | None = None,
) -> None:
    if db is None:
        return
    from app.common.services.audit_service import log_event

    details: dict = {
        "to": to_email,
        "subject": subject,
        "body_text": body_text,
        "sent": sent,
    }
    if body_html is not None:
        details["body_html"] = body_html
    if response_details is not None:
        details["response"] = response_details

    log_event(
        db,
        event_type="email_sent",
        area=area,
        actor_role="system",
        details=details,
    )
