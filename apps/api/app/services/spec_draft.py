"""
AI-facing draft schema for ScheduleSpec — the structured-outputs contract.

Claude never emits a ScheduleSpec directly. It emits SpecDraft / SpecUpdateDraft:
  - all times are "HH:MM" strings (LLMs are reliable with clock times, not
    minute arithmetic); "00:00" as an *end* time means midnight (1440)
  - quota counts are a list of {duration_h, count_per_week} objects (JSON
    Schema for structured outputs does not allow free-form dict keys)
  - every draft is converted deterministically to the engine's ScheduleSpec
    and re-validated, so a hallucinated field fails loudly here — never in
    the solver.

Updates are diffs (client briefs are cumulative — script #2 arrived as
feedback on script #1's schedule): add/replace/remove of shifts and rules,
applied by apply_update() with version bump.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, BeforeValidator, Field

from packages.scheduler.spec import (
    CoverageRule,
    DayShiftRestrictionRule,
    DaySelector,
    FairnessRule,
    OffRequestRule,
    Rule,
    ScheduleSpec,
    SequenceRule,
    ShiftDef,
    ShiftSelector,
    StaffMember,
    StartSpreadRule,
    WeeklyQuotaRule,
)


# LLMs (Gemini in particular) emit explicit nulls for optional object fields;
# a null days-selector means "every day".
DaysField = Annotated[DaySelector, BeforeValidator(lambda v: {} if v is None else v)]


def hhmm_to_min(value: str, is_end: bool = False) -> int:
    h, m = value.strip().split(":")
    minutes = int(h) * 60 + int(m)
    if minutes == 0 and is_end:
        return 1440  # "00:00" as an end time = midnight
    if not (0 <= minutes < 1440):
        raise ValueError(f"invalid time {value!r}")
    return minutes


def min_to_hhmm(minutes: int) -> str:
    return f"{(minutes % 1440) // 60:02d}:{minutes % 60:02d}"


# ─── Draft building blocks ────────────────────────────────────────────────────

class ShiftDraft(BaseModel):
    id: str = Field(description="Short unique code, e.g. 'A' or '0800-1600'")
    start: str = Field(description='Start time "HH:MM"')
    end: str = Field(description='End time "HH:MM"; "00:00" means midnight')
    preferred: bool = Field(default=True, description="False for fallback shifts used only when needed")
    color_hex: str = "#B3D9FF"
    allowed_weekdays: Optional[list[int]] = Field(
        default=None, description="Mon=0..Sun=6; e.g. [4,5,6] for weekend-only shifts. Omit for any day.")

    def to_shift(self) -> ShiftDef:
        return ShiftDef(
            id=self.id,
            start_min=hhmm_to_min(self.start),
            end_min=hhmm_to_min(self.end, is_end=True),
            preferred=self.preferred,
            color_hex=self.color_hex,
            allowed_weekdays=self.allowed_weekdays,
        )


class SelectorDraft(BaseModel):
    """Which shifts a rule refers to. Set only the fields needed; all set
    fields must match."""
    shift_ids: Optional[list[str]] = None
    min_duration_h: Optional[float] = None
    max_duration_h: Optional[float] = None
    starts_at_or_after: Optional[str] = Field(default=None, description='"HH:MM"')
    starts_at_or_before: Optional[str] = Field(default=None, description='"HH:MM"')
    ends_at_or_after: Optional[str] = Field(default=None, description='"HH:MM"; "00:00" = midnight')
    ends_at_or_before: Optional[str] = Field(default=None, description='"HH:MM"; "00:00" = midnight')

    def to_selector(self) -> ShiftSelector:
        return ShiftSelector(
            shift_ids=self.shift_ids,
            min_duration_h=self.min_duration_h,
            max_duration_h=self.max_duration_h,
            starts_at_or_after_min=None if self.starts_at_or_after is None else hhmm_to_min(self.starts_at_or_after),
            starts_at_or_before_min=None if self.starts_at_or_before is None else hhmm_to_min(self.starts_at_or_before),
            ends_at_or_after_min=None if self.ends_at_or_after is None else hhmm_to_min(self.ends_at_or_after, True),
            ends_at_or_before_min=None if self.ends_at_or_before is None else hhmm_to_min(self.ends_at_or_before, True),
        )


class RuleDraftBase(BaseModel):
    id: str = Field(description="Short unique snake_case id, e.g. 'never_close_alone'")
    description: str = Field(default="", description="One line, in the manager's language")
    enforcement: Literal["hard", "soft"] = Field(
        default="hard",
        description="hard = must hold ('задължително'); soft = minimise violations ('максимално да се избягва')")
    weight: int = Field(default=100, ge=1, description="Penalty per violation when soft")
    relaxable: bool = Field(
        default=False,
        description="True when the brief says 'if mathematically impossible, get as close as possible'")
    relax_priority: int = Field(default=100, description="Lower relaxes first")
    auto_repair: bool = Field(
        default=False,
        description="True when the brief demands post-generation checks with automatic rework until the rule holds")


class QuotaCountDraft(BaseModel):
    duration_h: float
    count_per_week: int


class WeeklyQuotaDraft(RuleDraftBase):
    type: Literal["weekly_quota"] = "weekly_quota"
    staff_ids: Optional[list[str]] = Field(default=None, description="Omit = everyone")
    quotas: list[QuotaCountDraft]
    rest_days_per_week: int = 0

    def to_rule(self) -> WeeklyQuotaRule:
        return WeeklyQuotaRule(
            **_base(self),
            staff_ids=self.staff_ids,
            shifts_per_duration={q.duration_h: q.count_per_week for q in self.quotas},
            rest_days_per_week=self.rest_days_per_week,
        )


class DayShiftRestrictionDraft(RuleDraftBase):
    type: Literal["day_shift_restriction"] = "day_shift_restriction"
    days: DaysField = Field(default_factory=DaySelector)
    allowed: SelectorDraft

    def to_rule(self) -> DayShiftRestrictionRule:
        return DayShiftRestrictionRule(**_base(self), days=self.days, allowed=self.allowed.to_selector())


class CoverageDraft(RuleDraftBase):
    type: Literal["coverage"] = "coverage"
    days: DaysField = Field(default_factory=DaySelector)
    window_start: str = Field(description='"HH:MM"')
    window_end: str = Field(description='"HH:MM"; "00:00" = midnight')
    min_staff: Optional[int] = None
    max_staff: Optional[int] = None

    def to_rule(self) -> CoverageRule:
        return CoverageRule(
            **_base(self), days=self.days,
            window_start_min=hhmm_to_min(self.window_start),
            window_end_min=hhmm_to_min(self.window_end, True),
            min_staff=self.min_staff, max_staff=self.max_staff,
        )


class StartSpreadDraft(RuleDraftBase):
    type: Literal["start_spread"] = "start_spread"
    days: DaysField = Field(default_factory=DaySelector)
    window_start: str = Field(description='Start-time window begin, "HH:MM"')
    window_end: str = Field(description='Start-time window end, "HH:MM"')
    max_starts: int

    def to_rule(self) -> StartSpreadRule:
        return StartSpreadRule(
            **_base(self), days=self.days,
            window_start_min=hhmm_to_min(self.window_start),
            window_end_min=hhmm_to_min(self.window_end, True),
            max_starts=self.max_starts,
        )


class SequenceDraft(RuleDraftBase):
    type: Literal["sequence"] = "sequence"
    mode: Literal["forbid", "require"]
    first: SelectorDraft
    second: SelectorDraft
    staff_ids: Optional[list[str]] = None
    weeks: Optional[list[int]] = Field(default=None, description="0-indexed weeks; require-mode only")

    def to_rule(self) -> SequenceRule:
        return SequenceRule(
            **_base(self), mode=self.mode,
            first=self.first.to_selector(), second=self.second.to_selector(),
            staff_ids=self.staff_ids, weeks=self.weeks,
        )


class FairnessDraft(RuleDraftBase):
    type: Literal["fairness"] = "fairness"
    shifts: SelectorDraft
    days: DaysField = Field(default_factory=DaySelector)
    staff_ids: Optional[list[str]] = None
    max_spread: int = 1

    def to_rule(self) -> FairnessRule:
        return FairnessRule(
            **_base(self), shifts=self.shifts.to_selector(), days=self.days,
            staff_ids=self.staff_ids, max_spread=self.max_spread,
        )


class OffRequestDraft(RuleDraftBase):
    type: Literal["off_request"] = "off_request"
    staff_id: str
    dates: list[date]

    def to_rule(self) -> OffRequestRule:
        return OffRequestRule(**_base(self), staff_id=self.staff_id, dates=self.dates)


def _base(d: RuleDraftBase) -> dict:
    return dict(
        id=d.id, description=d.description, enforcement=d.enforcement,
        weight=d.weight, relaxable=d.relaxable, relax_priority=d.relax_priority,
        auto_repair=d.auto_repair,
    )


RuleDraft = Annotated[
    Union[
        WeeklyQuotaDraft,
        DayShiftRestrictionDraft,
        CoverageDraft,
        StartSpreadDraft,
        SequenceDraft,
        FairnessDraft,
        OffRequestDraft,
    ],
    Field(discriminator="type"),
]


# ─── Draft roots ──────────────────────────────────────────────────────────────

class SpecDraft(BaseModel):
    """Full interpretation of a first brief."""
    venue_name: str = ""
    open_time: str = "08:00"
    close_time: str = "00:00"
    start_date: date
    num_days: int
    staff: list[StaffMember]
    shifts: list[ShiftDraft]
    rules: list[RuleDraft]
    summary_bg: str = Field(default="", description="Кратко резюме на интерпретираните правила, на български")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Anything ambiguous in the brief that required an assumption — the manager must confirm these")

    def to_spec(self) -> ScheduleSpec:
        return ScheduleSpec(
            venue_name=self.venue_name,
            open_min=hhmm_to_min(self.open_time),
            close_min=hhmm_to_min(self.close_time, True),
            start_date=self.start_date,
            num_days=self.num_days,
            staff=self.staff,
            shifts=[s.to_shift() for s in self.shifts],
            rules=[r.to_rule() for r in self.rules],
        )


class SpecUpdateDraft(BaseModel):
    """Diff of a follow-up brief against the current spec (cumulative — never
    a replacement)."""
    add_shifts: list[ShiftDraft] = Field(default_factory=list)
    replace_shifts: list[ShiftDraft] = Field(
        default_factory=list,
        description="Shifts whose id already exists; replaced in full (e.g. to promote a fallback shift to preferred)")
    remove_shift_ids: list[str] = Field(default_factory=list)
    add_rules: list[RuleDraft] = Field(default_factory=list)
    replace_rules: list[RuleDraft] = Field(
        default_factory=list, description="Rules whose id already exists; replaced in full")
    remove_rule_ids: list[str] = Field(default_factory=list)
    summary_bg: str = ""
    assumptions: list[str] = Field(default_factory=list)


def apply_update(spec: ScheduleSpec, update: SpecUpdateDraft) -> ScheduleSpec:
    """Deterministically apply a parsed diff; bumps the spec version. Raises
    on id collisions/misses so a bad diff fails loudly before solving."""
    shifts: list[ShiftDef] = [s for s in spec.shifts if s.id not in update.remove_shift_ids]
    shift_idx = {s.id: i for i, s in enumerate(shifts)}
    for draft in update.replace_shifts:
        if draft.id not in shift_idx:
            raise ValueError(f"replace_shifts: no shift with id {draft.id!r}")
        shifts[shift_idx[draft.id]] = draft.to_shift()
    for draft in update.add_shifts:
        if draft.id in shift_idx:
            raise ValueError(f"add_shifts: shift id {draft.id!r} already exists — use replace_shifts")
        shift_idx[draft.id] = len(shifts)
        shifts.append(draft.to_shift())

    rules: list[Rule] = [r for r in spec.rules if r.id not in update.remove_rule_ids]
    rules_by_id = {r.id: i for i, r in enumerate(rules)}
    for draft in update.replace_rules:
        if draft.id not in rules_by_id:
            raise ValueError(f"replace_rules: no rule with id {draft.id!r}")
        rules[rules_by_id[draft.id]] = draft.to_rule()
    for draft in update.add_rules:
        if draft.id in rules_by_id:
            raise ValueError(f"add_rules: rule id {draft.id!r} already exists — use replace_rules")
        rules.append(draft.to_rule())

    new_spec = spec.model_copy(deep=True, update={"shifts": shifts, "rules": rules, "version": spec.version + 1})
    return ScheduleSpec.model_validate(new_spec.model_dump())  # re-validate everything
