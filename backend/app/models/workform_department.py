"""WorkformDepartment and DepartmentHead models, copied from Airtable."""

from sqlalchemy import Column, Integer, String, UniqueConstraint
from app.database import Base


class WorkformDepartment(Base):
    """
    A department staff can report workform hours in (KALX Workforms).

    Copied from the Airtable "Department Heads" table by the staff sync. The
    workforms table has "<name> : Hours", "<name> : Description" and
    "<name> : Approved" columns for each one.
    """

    __tablename__ = "workform_departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)


class DepartmentHead(Base):
    """
    A head of a department, from the Airtable "Department Heads" table.

    Keyed on the head's Airtable staff record ID (Staff.airtable_record_id),
    since the "Department Heads" field links to the staff table.
    """

    __tablename__ = "department_heads"

    id = Column(Integer, primary_key=True, index=True)
    department = Column(String, nullable=False, index=True)
    staff_airtable_record_id = Column(String, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "department", "staff_airtable_record_id", name="uq_department_head"
        ),
    )
