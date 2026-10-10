"""Audit logging service — write structured event records to the audit_log table."""

import logging
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_event(
    db: Session,
    event_type: str,
    actor_email: str | None = None,
    actor_role: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
) -> None:
    """
    Write an audit log entry.

    Exceptions are caught and logged so this never breaks the caller's operation.

    :param db: Database session.
    :param event_type: Short string identifying the event (e.g. ``pass_given_away``).
    :param actor_email: Email of the person who triggered the event, or ``None`` for system events.
    :param actor_role: Role of the actor (``promotions``, ``staff``, ``dj``, ``system``).
    :param entity_type: Type of the primary entity involved (``pass``, ``show``, ``venue``, etc.).
    :param entity_id: Database ID of the primary entity.
    :param details: Arbitrary key/value pairs with event-specific context.
    """
    try:
        entry = AuditLog(
            event_type=event_type,
            actor_email=actor_email,
            actor_role=actor_role,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
        logger.error(
            "Failed to write audit log entry for event_type=%s", event_type, exc_info=True
        )
