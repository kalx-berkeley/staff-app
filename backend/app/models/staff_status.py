"""StaffStatus model — records status values for staff members."""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class StaffStatus(Base):
    """Associates a staff member with a status value (e.g. 'Active', 'Paid Staff')."""

    __tablename__ = "staff_statuses"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    status = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint("staff_id", "status", name="uq_staff_status"),)

    staff = relationship("Staff", back_populates="statuses")
