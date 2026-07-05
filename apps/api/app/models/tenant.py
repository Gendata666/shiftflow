from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum

from app.core.database import Base
from app.core.timeutil import utcnow


class Plan(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    plan: Mapped[Plan] = mapped_column(SAEnum(Plan), default=Plan.FREE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    venues = relationship("Venue", back_populates="tenant", cascade="all, delete-orphan")
    shift_types = relationship("ShiftType", back_populates="tenant", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="tenant", cascade="all, delete-orphan")
