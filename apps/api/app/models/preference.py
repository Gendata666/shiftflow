from sqlalchemy import String, DateTime, Date, JSON, ForeignKey, Enum as SAEnum, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
import enum

from app.core.database import Base


class PrefSource(str, enum.Enum):
    TELEGRAM = "TELEGRAM"
    WHATSAPP = "WHATSAPP"
    VIBER = "VIBER"
    WEB = "WEB"


class PrefType(str, enum.Enum):
    OFF_REQUEST = "OFF_REQUEST"
    PREFERRED_SHIFT = "PREFERRED_SHIFT"
    UNAVAILABLE = "UNAVAILABLE"
    NOTES = "NOTES"


class PrefStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    staff_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    period_id: Mapped[str | None] = mapped_column(String, ForeignKey("schedule_periods.id"), index=True)
    source: Mapped[PrefSource] = mapped_column(SAEnum(PrefSource), nullable=False)
    type: Mapped[PrefType] = mapped_column(SAEnum(PrefType), nullable=False)
    target_dates: Mapped[list] = mapped_column(JSON, default=list)
    raw_message: Mapped[str | None] = mapped_column(String)
    parsed_json: Mapped[dict | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(String)
    status: Mapped[PrefStatus] = mapped_column(SAEnum(PrefStatus), default=PrefStatus.PENDING)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    staff = relationship("User", back_populates="preferences")
    period = relationship("SchedulePeriod", back_populates="preferences")
