from sqlalchemy import String, DateTime, Boolean, Date, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
import enum

from app.core.database import Base


class PeriodStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class SchedulePeriod(Base):
    __tablename__ = "schedule_periods"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, index=True)
    venue_id: Mapped[str] = mapped_column(String, ForeignKey("venues.id"), index=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PeriodStatus] = mapped_column(SAEnum(PeriodStatus), default=PeriodStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schedules = relationship("Schedule", back_populates="period")
    preferences = relationship("Preference", back_populates="period")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    venue_id: Mapped[str] = mapped_column(String, ForeignKey("venues.id"))
    period_id: Mapped[str] = mapped_column(String, ForeignKey("schedule_periods.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(String)

    tenant = relationship("Tenant", back_populates="schedules")
    venue = relationship("Venue", back_populates="schedules")
    period = relationship("SchedulePeriod", back_populates="schedules")
    assignments = relationship("ShiftAssignment", back_populates="schedule", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="schedule")


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    schedule_id: Mapped[str] = mapped_column(String, ForeignKey("schedules.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[str] = mapped_column(String, ForeignKey("staff_profiles.id"))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_type_id: Mapped[str] = mapped_column(String, ForeignKey("shift_types.id"))
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    schedule = relationship("Schedule", back_populates="assignments")
    staff = relationship("StaffProfile", back_populates="shift_assignments")
    shift_type = relationship("ShiftType", back_populates="shift_assignments")
