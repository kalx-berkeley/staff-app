"""AuditLog model — append-only table for tracking significant app events."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.database import Base


class AuditLog(Base):
    """Append-only audit log for significant events."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    occurred_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    event_type = Column(String, nullable=False, index=True)
    actor_email = Column(String, nullable=True)
    actor_role = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
