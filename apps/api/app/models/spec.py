from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
import enum

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SpecStatus(str, enum.Enum):
    DRAFT = "DRAFT"        # parsed, awaiting manager confirmation
    ACTIVE = "ACTIVE"      # confirmed — the venue's current rulebook
    ARCHIVED = "ARCHIVED"


class SpecRecord(Base):
    """A versioned ScheduleSpec (the venue's rulebook). spec_json is the
    engine's ScheduleSpec serialised; new versions are new rows so client
    iterations stay auditable."""
    __tablename__ = "schedule_specs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    venue_id: Mapped[str | None] = mapped_column(String, ForeignKey("venues.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[SpecStatus] = mapped_column(SAEnum(SpecStatus), default=SpecStatus.DRAFT)
    spec_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_brief: Mapped[str | None] = mapped_column(Text)   # the raw manager brief
    summary: Mapped[str | None] = mapped_column(Text)        # AI interpretation summary (BG)
    created_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class RunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    INFEASIBLE = "INFEASIBLE"
    ERROR = "ERROR"


class ScheduleRun(Base):
    """One solver execution: which spec version ran and the full
    GenerateReport (assignments + verification findings)."""
    __tablename__ = "schedule_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    spec_id: Mapped[str] = mapped_column(String, ForeignKey("schedule_specs.id", ondelete="CASCADE"), index=True)
    status: Mapped[RunStatus] = mapped_column(SAEnum(RunStatus), default=RunStatus.RUNNING)
    report_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
