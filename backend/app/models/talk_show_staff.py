"""TalkShowStaff model — maps Talk & Information shows to their staff members."""

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class TalkShowStaff(Base):
    """
    A staff member of a Talk & Information show.

    Talk & Information shows are specialty shows with category "talk". Their
    members are staff members rather than DJ names, and can reserve on-air pass
    pairs for the show.
    """

    __tablename__ = "talk_show_staff"
    __table_args__ = (UniqueConstraint("specialty_show_id", "staff_id"),)

    id = Column(Integer, primary_key=True)
    specialty_show_id = Column(
        Integer, ForeignKey("specialty_shows.id", ondelete="CASCADE"), nullable=False
    )
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False, index=True)

    specialty_show = relationship("SpecialtyShow", back_populates="staff_members")
    staff = relationship("Staff")

    @property
    def staff_email(self) -> str | None:
        return self.staff.email if self.staff else None
