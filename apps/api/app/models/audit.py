from sqlalchemy import String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.core.database import Base
from app.core.timeutil import utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, index=True)
    actor_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    schedule_id: Mapped[str | None] = mapped_column(String, ForeignKey("schedules.id"))
    action: Mapped[str] = mapped_column(String, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    actor = relationship("User")
    schedule = relationship("Schedule", back_populates="audit_logs")
