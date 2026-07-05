"""
ScheduleSpec — the constraint vocabulary of ShiftFlow.

This is the contract between the AI layer (which translates natural-language
briefs into a spec) and the solver/verifier (which interpret it). The AI never
produces schedules — only instances of this schema. Rules are cumulative and
versioned: follow-up client briefs merge into an existing spec.

Every rule carries an enforcement level:
  - hard              — must hold; solver fails/relaxes ladder otherwise
  - soft              — violations allowed, penalised by `weight`
  - relaxable (flag)  — a hard rule the infeasibility ladder may demote to a
                        penalty (lowest `relax_priority` first) when the model
                        is infeasible, per the client requirement "if
                        mathematically impossible, get as close as possible
                        and say so explicitly".

Time is expressed in minutes from midnight (0..1440); a shift ending at
midnight has end_min == 1440. OFF is a reserved pseudo-shift id.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

OFF = "OFF"  # reserved pseudo-shift id: a rest day

# Weekday numbers follow Python: Mon=0 .. Sun=6.
WEEKEND = [4, 5, 6]  # client convention: Fri/Sat/Sun
WEEKDAYS = [0, 1, 2, 3]


# ─── Building blocks ──────────────────────────────────────────────────────────

class StaffMember(BaseModel):
    id: str
    name: str
    role_label: Optional[str] = None
    active: bool = True


class ShiftDef(BaseModel):
    """One shift in the catalog. `preferred=False` marks fallback shifts the
    solver may use but should not favour ("могат да се използват при нужда")."""
    id: str
    label: str = ""
    start_min: int = Field(ge=0, lt=1440)
    end_min: int = Field(gt=0, le=1440)
    preferred: bool = True
    color_hex: str = "#B3D9FF"
    allowed_weekdays: Optional[list[int]] = None  # None = any day

    @model_validator(mode="after")
    def _check(self):
        if self.end_min <= self.start_min:
            raise ValueError(f"shift {self.id}: end_min must be > start_min (use 1440 for 00:00)")
        if not self.label:
            self.label = f"{self._fmt(self.start_min)}–{self._fmt(self.end_min)}"
        return self

    @staticmethod
    def _fmt(m: int) -> str:
        m = m % 1440
        return f"{m // 60:02d}:{m % 60:02d}"

    @property
    def duration_h(self) -> float:
        return (self.end_min - self.start_min) / 60

    def covers_hour(self, hour: int) -> bool:
        """True if staff on this shift are present during [hour, hour+1)."""
        return self.start_min <= hour * 60 and (hour + 1) * 60 <= self.end_min


class DaySelector(BaseModel):
    """Which days a rule applies to. Empty = every day of the horizon."""
    weekdays: Optional[list[int]] = None  # Mon=0..Sun=6
    dates: Optional[list[date]] = None

    def matches(self, d: date) -> bool:
        if self.dates is not None and d not in self.dates:
            return False
        if self.weekdays is not None and d.weekday() not in self.weekdays:
            return False
        return True


class ShiftSelector(BaseModel):
    """Predicate over the shift catalog. All set fields must match (AND).
    Never matches OFF."""
    shift_ids: Optional[list[str]] = None
    min_duration_h: Optional[float] = None
    max_duration_h: Optional[float] = None
    starts_at_or_after_min: Optional[int] = None
    starts_at_or_before_min: Optional[int] = None
    ends_at_or_after_min: Optional[int] = None
    ends_at_or_before_min: Optional[int] = None

    def matches(self, s: ShiftDef) -> bool:
        if self.shift_ids is not None and s.id not in self.shift_ids:
            return False
        if self.min_duration_h is not None and s.duration_h < self.min_duration_h:
            return False
        if self.max_duration_h is not None and s.duration_h > self.max_duration_h:
            return False
        if self.starts_at_or_after_min is not None and s.start_min < self.starts_at_or_after_min:
            return False
        if self.starts_at_or_before_min is not None and s.start_min > self.starts_at_or_before_min:
            return False
        if self.ends_at_or_after_min is not None and s.end_min < self.ends_at_or_after_min:
            return False
        if self.ends_at_or_before_min is not None and s.end_min > self.ends_at_or_before_min:
            return False
        return True


# ─── Rules ────────────────────────────────────────────────────────────────────

class RuleBase(BaseModel):
    id: str
    description: str = ""
    enforcement: Literal["hard", "soft"] = "hard"
    weight: int = Field(default=100, ge=1)  # penalty per violation when soft
    relaxable: bool = False                 # hard rule the ladder may demote
    relax_priority: int = 100               # lower = relaxed first
    # Client script #2, rule 7: "if a check fails, automatically rework the
    # schedule until all rules hold". A violated soft rule with auto_repair
    # is escalated to hard (and relaxable) by the orchestrator and re-solved.
    auto_repair: bool = False


class WeeklyQuotaRule(RuleBase):
    """Per staff member, per week: exact shift counts per duration group and
    rest days ("всяка седмица всеки има 2×8ч + 2×10ч + 3×12ч").
    Weeks with approved off-requests get elastic quotas (<=) with penalised
    deviation, since the forced OFF must displace some shift."""
    type: Literal["weekly_quota"] = "weekly_quota"
    staff_ids: Optional[list[str]] = None  # None = everyone
    shifts_per_duration: dict[float, int]  # duration hours -> count/week
    rest_days_per_week: int = Field(default=0, ge=0)


class DayShiftRestrictionRule(RuleBase):
    """On matching days, any worked shift must match the selector
    ("петък/събота/неделя всички работят само 12-часови смени")."""
    type: Literal["day_shift_restriction"] = "day_shift_restriction"
    days: DaySelector = Field(default_factory=DaySelector)
    allowed: ShiftSelector


class CoverageRule(RuleBase):
    """Bound the number of staff present during a time window on matching
    days. This single mechanism expresses "exactly 2 closers on weekends",
    "never close alone" (min 2 in the closing window), "even coverage all
    day" and "1 person 08–10 on weekdays is fine"."""
    type: Literal["coverage"] = "coverage"
    days: DaySelector = Field(default_factory=DaySelector)
    window_start_min: int = Field(ge=0, lt=1440)
    window_end_min: int = Field(gt=0, le=1440)
    min_staff: Optional[int] = None
    max_staff: Optional[int] = None

    @model_validator(mode="after")
    def _check(self):
        if self.window_end_min <= self.window_start_min:
            raise ValueError(f"coverage rule {self.id}: window_end_min must be > window_start_min")
        if self.min_staff is None and self.max_staff is None:
            raise ValueError(f"coverage rule {self.id}: set min_staff and/or max_staff")
        return self

    def hours(self) -> range:
        return range(self.window_start_min // 60, (self.window_end_min + 59) // 60)


class StartSpreadRule(RuleBase):
    """Anti-clustering: at most `max_starts` staff may start within the
    window on matching days ("не допускай всички да бъдат първа смяна")."""
    type: Literal["start_spread"] = "start_spread"
    days: DaySelector = Field(default_factory=DaySelector)
    window_start_min: int = Field(ge=0, lt=1440)
    window_end_min: int = Field(gt=0, le=1440)
    max_starts: int = Field(ge=0)


class SequenceRule(RuleBase):
    """Consecutive-day shift patterns.
      mode="forbid":  first-shift day d + second-shift day d+1 is a violation
                      (hard: never; soft: minimised & counted — the "16:00–00:00
                      then 08:00–16:00" rule).
      mode="require": each (staff, listed week) must contain the sequence at
                      least once (the "reward" 08–16 → 16–00 rotation).
    """
    type: Literal["sequence"] = "sequence"
    mode: Literal["forbid", "require"]
    first: ShiftSelector
    second: ShiftSelector
    staff_ids: Optional[list[str]] = None
    weeks: Optional[list[int]] = None  # 0-indexed weeks; require-mode only


class FairnessRule(RuleBase):
    """Distribute matching shifts evenly across staff ("късните смени да се
    разпределят равномерно"). Hard: max-min count spread <= max_spread.
    Soft: minimise the spread, weighted."""
    type: Literal["fairness"] = "fairness"
    shifts: ShiftSelector
    days: DaySelector = Field(default_factory=DaySelector)
    staff_ids: Optional[list[str]] = None
    max_spread: int = Field(default=1, ge=0)


class OffRequestRule(RuleBase):
    """Approved staff off-request: forced OFF on the given dates."""
    type: Literal["off_request"] = "off_request"
    staff_id: str
    dates: list[date]


Rule = Annotated[
    Union[
        WeeklyQuotaRule,
        DayShiftRestrictionRule,
        CoverageRule,
        StartSpreadRule,
        SequenceRule,
        FairnessRule,
        OffRequestRule,
    ],
    Field(discriminator="type"),
]


# ─── The spec ─────────────────────────────────────────────────────────────────

class ScheduleSpec(BaseModel):
    """A complete, versioned rulebook for one scheduling period."""
    version: int = 1
    venue_name: str = ""
    open_min: int = Field(default=480, ge=0, lt=1440)    # venue opens (08:00)
    close_min: int = Field(default=1440, gt=0, le=1440)  # venue closes (00:00)
    start_date: date
    num_days: int = Field(ge=1, le=62)
    staff: list[StaffMember]
    shifts: list[ShiftDef]
    rules: list[Rule] = Field(default_factory=list)
    time_limit_seconds: int = Field(default=30, ge=1, le=300)

    @field_validator("shifts")
    @classmethod
    def _no_off_collision(cls, v: list[ShiftDef]):
        ids = [s.id for s in v]
        if OFF in ids:
            raise ValueError(f"'{OFF}' is a reserved shift id")
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate shift ids")
        return v

    @model_validator(mode="after")
    def _check_rules(self):
        staff_ids = {s.id for s in self.staff}
        rule_ids = set()
        for r in self.rules:
            if r.id in rule_ids:
                raise ValueError(f"duplicate rule id {r.id!r}")
            rule_ids.add(r.id)
            for sid in getattr(r, "staff_ids", None) or []:
                if sid not in staff_ids:
                    raise ValueError(f"rule {r.id}: unknown staff id {sid!r}")
            if isinstance(r, OffRequestRule) and r.staff_id not in staff_ids:
                raise ValueError(f"rule {r.id}: unknown staff id {r.staff_id!r}")
        return self

    # Convenience -------------------------------------------------------------

    def days(self) -> list[date]:
        return [self.start_date + timedelta(days=i) for i in range(self.num_days)]

    def week_of_day(self, day_index: int) -> int:
        return day_index // 7

    def num_weeks(self) -> int:
        return (self.num_days + 6) // 7

    def shift_by_id(self, shift_id: str) -> ShiftDef:
        for s in self.shifts:
            if s.id == shift_id:
                return s
        raise KeyError(shift_id)

    def rule_by_id(self, rule_id: str) -> Rule:
        for r in self.rules:
            if r.id == rule_id:
                return r
        raise KeyError(rule_id)


# ─── Solve / verification result types ───────────────────────────────────────

class Assignment(BaseModel):
    staff_id: str
    date: date
    shift_id: str  # a catalog shift id, or OFF


class Finding(BaseModel):
    """One verifier finding for one rule."""
    rule_id: str
    rule_type: str
    status: Literal["ok", "violated", "relaxed"]
    violations: int = 0
    cells: list[str] = Field(default_factory=list)  # "staff_id@YYYY-MM-DD" refs
    message_en: str = ""
    message_bg: str = ""


class SolveResult(BaseModel):
    status: Literal["optimal", "feasible", "infeasible"]
    assignments: list[Assignment] = Field(default_factory=list)
    relaxed_rule_ids: list[str] = Field(default_factory=list)
    violation_counts: dict[str, int] = Field(default_factory=dict)  # rule id -> count
    objective_value: int = 0
    solver_status: str = ""


class GenerateReport(BaseModel):
    """Full outcome of the solve → verify → repair pipeline."""
    result: SolveResult
    findings: list[Finding] = Field(default_factory=list)
    repair_iterations: int = 0
    escalated_rule_ids: list[str] = Field(default_factory=list)

    @property
    def clean(self) -> bool:
        return all(f.status == "ok" for f in self.findings)
