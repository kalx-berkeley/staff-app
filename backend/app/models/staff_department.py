"""StaffDepartment model — records department memberships for all staff."""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class StaffDepartment(Base):
    """Associates a staff member with a department name."""

    __tablename__ = "staff_departments"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    department = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("staff_id", "department", name="uq_staff_department"),
    )

    staff = relationship("Staff", back_populates="departments")
