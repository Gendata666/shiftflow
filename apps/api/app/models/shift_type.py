from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.core.database import Base
from app.core.timeutil import utcnow


class ShiftType(Base):
    __tablename__ = "shift_types"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    start_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    start_min: Mapped[int] = mapped_column(Integer, default=0)
    end_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    end_min: Mapped[int] = mapped_column(Integer, default=0)
    duration_h: Mapped[int] = mapped_column(Integer, nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), default="#B3D9FF")
    weekend_only: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    tenant = relationship("Tenant", back_populates="shift_types")
    shift_assignments = relationship("ShiftAssignment", back_populates="shift_type")
