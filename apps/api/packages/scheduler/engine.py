"""
ShiftFlow Engine v2 — spec-driven CP-SAT solver with a rule registry.

The engine interprets a ScheduleSpec generically: every rule type has a
handler that (a) adds constraints/penalties to the CP-SAT model and (b) is
mirrored by an independent verify() in verifier.py. New client-specific
constraint types are added by registering one handler — the core never
changes.

Infeasibility ladder: solve strict first; if INFEASIBLE, demote `relaxable`
hard rules (lowest relax_priority first, cumulatively) to high-weight
penalties and re-solve, so the client always gets the closest possible
schedule plus an explicit report of what could not be satisfied.

The legacy dataclass API (ScheduleConfig/solve) is kept as a thin adapter on
top of the spec engine for the existing router and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from ortools.sat.python import cp_model

from packages.scheduler.spec import (
    OFF,
    Assignment,
    CoverageRule,
    DayShiftRestrictionRule,
    FairnessRule,
    OffRequestRule,
    ScheduleSpec,
    SequenceRule,
    ShiftDef,
    SolveResult,
    StartSpreadRule,
    WeeklyQuotaRule,
)

# Penalty multiplier for hard rules demoted by the infeasibility ladder —
# violating a relaxed rule must always dominate ordinary soft penalties.
RELAXED_MULTIPLIER = 10
# Tiny penalty per use of a non-preferred (fallback) shift.
FALLBACK_SHIFT_WEIGHT = 1
PREFERRED_PSEUDO_RULE = "__prefer_preferred_shifts__"


# ─── Build context ────────────────────────────────────────────────────────────

class _Ctx:
    """Everything a rule handler needs while building the model."""

    def __init__(self, spec: ScheduleSpec):
        self.spec = spec
        self.model = cp_model.CpModel()
        self.days: list[date] = spec.days()
        self.staff_ids = [s.id for s in spec.staff if s.active]
        self.shift_ids = [s.id for s in spec.shifts] + [OFF]
        self.shifts = {s.id: s for s in spec.shifts}
        # x[(staff_id, day_index, shift_id)] — includes OFF
        self.x: dict[tuple[str, int, str], cp_model.IntVar] = {}
        # rule_id -> list of 0/1|int vars counting violations
        self.violation_vars: dict[str, list] = {}
        # (rule_id, weight, var) objective terms
        self.penalty_terms: list[tuple[str, int, object]] = []

        for sid in self.staff_ids:
            for d in range(spec.num_days):
                for k in self.shift_ids:
                    self.x[(sid, d, k)] = self.model.new_bool_var(f"x_{sid}_{d}_{k}")

        # Structural: exactly one assignment (a shift or OFF) per staff-day.
        for sid in self.staff_ids:
            for d in range(spec.num_days):
                self.model.add_exactly_one(self.x[(sid, d, k)] for k in self.shift_ids)

        # Structural: shift-level weekday restrictions (e.g. weekend-only shifts).
        for shift in spec.shifts:
            if shift.allowed_weekdays is not None:
                allowed = set(shift.allowed_weekdays)
                for d, day in enumerate(self.days):
                    if day.weekday() not in allowed:
                        for sid in self.staff_ids:
                            self.model.add(self.x[(sid, d, shift.id)] == 0)

        # Structural soft: prefer preferred shifts over fallback ones.
        for shift in spec.shifts:
            if not shift.preferred:
                for sid in self.staff_ids:
                    for d in range(spec.num_days):
                        self.penalty_terms.append(
                            (PREFERRED_PSEUDO_RULE, FALLBACK_SHIFT_WEIGHT, self.x[(sid, d, shift.id)])
                        )

    # Helpers ------------------------------------------------------------------

    def staff_in_scope(self, staff_ids) -> list[str]:
        return [s for s in self.staff_ids if staff_ids is None or s in staff_ids]

    def matching_shifts(self, selector) -> list[ShiftDef]:
        return [s for s in self.spec.shifts if selector.matches(s)]

    def week_day_indices(self, week: int) -> list[int]:
        return list(range(week * 7, min((week + 1) * 7, self.spec.num_days)))

    def is_full_week(self, week: int) -> bool:
        return len(self.week_day_indices(week)) == 7

    def presence(self, d: int, hour: int):
        """Sum of staff present during [hour, hour+1) on day d."""
        terms = []
        for shift in self.spec.shifts:
            if shift.covers_hour(hour):
                for sid in self.staff_ids:
                    terms.append(self.x[(sid, d, shift.id)])
        return sum(terms) if terms else 0

    def add_violation(self, rule_id: str, weight: int, var) -> None:
        self.violation_vars.setdefault(rule_id, []).append(var)
        self.penalty_terms.append((rule_id, weight, var))

    def new_count_var(self, ub: int, name: str):
        return self.model.new_int_var(0, max(ub, 0), name)

    def forced_off_days(self, staff_id: str) -> set[int]:
        """Day indices forced OFF for this staff member by hard off-requests."""
        out: set[int] = set()
        for r in self.spec.rules:
            if isinstance(r, OffRequestRule) and r.staff_id == staff_id and r.enforcement == "hard":
                for dt in r.dates:
                    idx = (dt - self.spec.start_date).days
                    if 0 <= idx < self.spec.num_days:
                        out.add(idx)
        return out


# ─── Rule handlers (model side) ──────────────────────────────────────────────
# Each handler: apply(rule, ctx, effective) where effective is "hard" or
# "soft"; soft includes ladder-relaxed hard rules (with boosted weight).

def _apply_weekly_quota(rule: WeeklyQuotaRule, ctx: _Ctx, effective: str, weight: int):
    dur_groups: dict[float, list[str]] = {}
    for shift in ctx.spec.shifts:
        dur_groups.setdefault(shift.duration_h, []).append(shift.id)

    for sid in ctx.staff_in_scope(rule.staff_ids):
        forced_off = ctx.forced_off_days(sid)
        for w in range(ctx.spec.num_weeks()):
            days = ctx.week_day_indices(w)
            n_days = len(days)
            forced_in_week = len([d for d in days if d in forced_off])
            elastic = (not ctx.is_full_week(w)) or forced_in_week > 0 or effective == "soft"

            off_count = sum(ctx.x[(sid, d, OFF)] for d in days)
            expected_off = min(rule.rest_days_per_week + forced_in_week, n_days)

            if not elastic:
                ctx.model.add(off_count == expected_off)
                for dur, quota in rule.shifts_per_duration.items():
                    shift_ids = dur_groups.get(dur, [])
                    count = sum(ctx.x[(sid, d, k)] for d in days for k in shift_ids)
                    ctx.model.add(count == quota)
            else:
                # Elastic: quotas become ceilings and every unit of deviation
                # is counted as a violation (weeks with forced OFF days, or a
                # soft/relaxed quota rule overall).
                off_dev = ctx.new_count_var(n_days, f"qoffdev_{rule.id}_{sid}_{w}")
                ctx.model.add(off_dev >= off_count - expected_off)
                ctx.model.add(off_dev >= expected_off - off_count)
                ctx.add_violation(rule.id, weight, off_dev)
                for dur, quota in rule.shifts_per_duration.items():
                    shift_ids = dur_groups.get(dur, [])
                    count = sum(ctx.x[(sid, d, k)] for d in days for k in shift_ids)
                    quota_eff = min(quota, n_days)
                    dev = ctx.new_count_var(n_days, f"qdev_{rule.id}_{sid}_{w}_{dur}")
                    ctx.model.add(dev >= count - quota_eff)
                    ctx.model.add(dev >= quota_eff - count)
                    ctx.add_violation(rule.id, weight, dev)


def _apply_day_shift_restriction(rule: DayShiftRestrictionRule, ctx: _Ctx, effective: str, weight: int):
    disallowed = [s.id for s in ctx.spec.shifts if not rule.allowed.matches(s)]
    for d, day in enumerate(ctx.days):
        if not rule.days.matches(day):
            continue
        for sid in ctx.staff_ids:
            for k in disallowed:
                if effective == "hard":
                    ctx.model.add(ctx.x[(sid, d, k)] == 0)
                else:
                    ctx.add_violation(rule.id, weight, ctx.x[(sid, d, k)])


def _apply_coverage(rule: CoverageRule, ctx: _Ctx, effective: str, weight: int):
    n_staff = len(ctx.staff_ids)
    for d, day in enumerate(ctx.days):
        if not rule.days.matches(day):
            continue
        for hour in rule.hours():
            present = ctx.presence(d, hour)
            if rule.min_staff is not None:
                if effective == "hard":
                    ctx.model.add(present >= rule.min_staff)
                else:
                    short = ctx.new_count_var(rule.min_staff, f"covshort_{rule.id}_{d}_{hour}")
                    ctx.model.add(short >= rule.min_staff - present)
                    ctx.add_violation(rule.id, weight, short)
            if rule.max_staff is not None:
                if effective == "hard":
                    ctx.model.add(present <= rule.max_staff)
                else:
                    over = ctx.new_count_var(n_staff, f"covover_{rule.id}_{d}_{hour}")
                    ctx.model.add(over >= present - rule.max_staff)
                    ctx.add_violation(rule.id, weight, over)


def _apply_start_spread(rule: StartSpreadRule, ctx: _Ctx, effective: str, weight: int):
    window_shifts = [
        s.id for s in ctx.spec.shifts
        if rule.window_start_min <= s.start_min < rule.window_end_min
    ]
    if not window_shifts:
        return
    n_staff = len(ctx.staff_ids)
    for d, day in enumerate(ctx.days):
        if not rule.days.matches(day):
            continue
        starts = sum(ctx.x[(sid, d, k)] for sid in ctx.staff_ids for k in window_shifts)
        if effective == "hard":
            ctx.model.add(starts <= rule.max_starts)
        else:
            over = ctx.new_count_var(n_staff, f"spreadover_{rule.id}_{d}")
            ctx.model.add(over >= starts - rule.max_starts)
            ctx.add_violation(rule.id, weight, over)


def _apply_sequence(rule: SequenceRule, ctx: _Ctx, effective: str, weight: int):
    first_ids = [s.id for s in ctx.matching_shifts(rule.first)]
    second_ids = [s.id for s in ctx.matching_shifts(rule.second)]
    if not first_ids or not second_ids:
        return

    if rule.mode == "forbid":
        for sid in ctx.staff_in_scope(rule.staff_ids):
            for d in range(ctx.spec.num_days - 1):
                first = sum(ctx.x[(sid, d, k)] for k in first_ids)
                second = sum(ctx.x[(sid, d + 1, k)] for k in second_ids)
                if effective == "hard":
                    ctx.model.add(first + second <= 1)
                else:
                    bad = ctx.model.new_bool_var(f"seqbad_{rule.id}_{sid}_{d}")
                    ctx.model.add(bad >= first + second - 1)
                    ctx.add_violation(rule.id, weight, bad)
    else:  # require: at least once per (staff, week)
        weeks = rule.weeks if rule.weeks is not None else list(range(ctx.spec.num_weeks()))
        for sid in ctx.staff_in_scope(rule.staff_ids):
            for w in weeks:
                days = ctx.week_day_indices(w)
                pair_vars = []
                for d in days[:-1]:  # both days inside the same week
                    first = sum(ctx.x[(sid, d, k)] for k in first_ids)
                    second = sum(ctx.x[(sid, d + 1, k)] for k in second_ids)
                    p = ctx.model.new_bool_var(f"seqreq_{rule.id}_{sid}_{d}")
                    ctx.model.add(p <= first)
                    ctx.model.add(p <= second)
                    pair_vars.append(p)
                if not pair_vars:
                    continue
                if effective == "hard":
                    ctx.model.add(sum(pair_vars) >= 1)
                else:
                    miss = ctx.model.new_bool_var(f"seqmiss_{rule.id}_{sid}_{w}")
                    ctx.model.add(miss >= 1 - sum(pair_vars))
                    ctx.add_violation(rule.id, weight, miss)


def _apply_fairness(rule: FairnessRule, ctx: _Ctx, effective: str, weight: int):
    shift_ids = [s.id for s in ctx.matching_shifts(rule.shifts)]
    scope = ctx.staff_in_scope(rule.staff_ids)
    if not shift_ids or len(scope) < 2:
        return
    day_idx = [d for d, day in enumerate(ctx.days) if rule.days.matches(day)]
    max_count = len(day_idx)
    counts = []
    for sid in scope:
        c = ctx.new_count_var(max_count, f"fair_{rule.id}_{sid}")
        ctx.model.add(c == sum(ctx.x[(sid, d, k)] for d in day_idx for k in shift_ids))
        counts.append(c)
    cmax = ctx.new_count_var(max_count, f"fairmax_{rule.id}")
    cmin = ctx.new_count_var(max_count, f"fairmin_{rule.id}")
    ctx.model.add_max_equality(cmax, counts)
    ctx.model.add_min_equality(cmin, counts)
    if effective == "hard":
        ctx.model.add(cmax - cmin <= rule.max_spread)
    else:
        over = ctx.new_count_var(max_count, f"fairover_{rule.id}")
        ctx.model.add(over >= cmax - cmin - rule.max_spread)
        ctx.add_violation(rule.id, weight, over)


def _apply_off_request(rule: OffRequestRule, ctx: _Ctx, effective: str, weight: int):
    if rule.staff_id not in ctx.staff_ids:
        return
    for dt in rule.dates:
        d = (dt - ctx.spec.start_date).days
        if not (0 <= d < ctx.spec.num_days):
            continue
        if effective == "hard":
            ctx.model.add(ctx.x[(rule.staff_id, d, OFF)] == 1)
        else:
            miss = ctx.model.new_bool_var(f"offmiss_{rule.id}_{d}")
            ctx.model.add(miss >= 1 - ctx.x[(rule.staff_id, d, OFF)])
            ctx.add_violation(rule.id, weight, miss)


HANDLERS = {
    "weekly_quota": _apply_weekly_quota,
    "day_shift_restriction": _apply_day_shift_restriction,
    "coverage": _apply_coverage,
    "start_spread": _apply_start_spread,
    "sequence": _apply_sequence,
    "fairness": _apply_fairness,
    "off_request": _apply_off_request,
}


# ─── Solve ────────────────────────────────────────────────────────────────────

def solve_spec(spec: ScheduleSpec, relaxed_rule_ids: set[str] | None = None) -> SolveResult:
    """One solve pass. Rules whose ids are in relaxed_rule_ids are demoted
    from hard constraints to boosted penalties."""
    relaxed_rule_ids = relaxed_rule_ids or set()
    ctx = _Ctx(spec)

    for rule in spec.rules:
        handler = HANDLERS[rule.type]
        if rule.enforcement == "hard" and rule.id not in relaxed_rule_ids:
            handler(rule, ctx, "hard", rule.weight)
        elif rule.id in relaxed_rule_ids:
            handler(rule, ctx, "soft", rule.weight * RELAXED_MULTIPLIER)
        else:
            handler(rule, ctx, "soft", rule.weight)

    if ctx.penalty_terms:
        ctx.model.minimize(sum(w * v for (_rid, w, v) in ctx.penalty_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = spec.time_limit_seconds
    solver.parameters.num_search_workers = 8
    status = solver.solve(ctx.model)
    status_name = solver.status_name(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(status="infeasible", solver_status=status_name,
                           relaxed_rule_ids=sorted(relaxed_rule_ids))

    assignments: list[Assignment] = []
    for sid in ctx.staff_ids:
        for d, day in enumerate(ctx.days):
            for k in ctx.shift_ids:
                if solver.value(ctx.x[(sid, d, k)]):
                    assignments.append(Assignment(staff_id=sid, date=day, shift_id=k))
                    break

    violation_counts = {
        rid: int(sum(solver.value(v) for v in vars_))
        for rid, vars_ in ctx.violation_vars.items()
    }
    return SolveResult(
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        assignments=assignments,
        relaxed_rule_ids=sorted(relaxed_rule_ids),
        violation_counts=violation_counts,
        objective_value=int(solver.objective_value) if ctx.penalty_terms else 0,
        solver_status=status_name,
    )


def solve_with_relaxation(spec: ScheduleSpec) -> SolveResult:
    """Infeasibility ladder: strict solve first; on INFEASIBLE, demote
    relaxable hard rules tier by tier (lowest relax_priority first,
    cumulative) until feasible or nothing is left to relax."""
    relaxed: set[str] = set()
    while True:
        result = solve_spec(spec, relaxed)
        if result.status != "infeasible":
            return result
        candidates = [
            r for r in spec.rules
            if r.enforcement == "hard" and r.relaxable and r.id not in relaxed
        ]
        if not candidates:
            return result
        tier = min(r.relax_priority for r in candidates)
        relaxed |= {r.id for r in candidates if r.relax_priority == tier}


# ─── Legacy adapter (keeps old router/tests working) ─────────────────────────

@dataclass
class ShiftTypeDef:
    id: str
    code: str
    start_hour: int
    end_hour: int
    duration_h: int
    weekend_only: bool = False
    color_hex: str = "#B3D9FF"

    @property
    def ends_midnight(self) -> bool:
        return self.end_hour == 0

    @property
    def starts_early(self) -> bool:
        return self.start_hour <= 8


@dataclass
class StaffDef:
    id: str
    name: str
    profile_id: str


@dataclass
class QuotaRule:
    duration_h: int
    count_per_week: int


@dataclass
class ScheduleConfig:
    staff: list[StaffDef]
    shift_types: list[ShiftTypeDef]
    start_date: date
    num_days: int
    quota_rules: list[QuotaRule]
    off_requests: dict[str, set[date]] = field(default_factory=dict)
    time_limit_seconds: int = 30


@dataclass
class LegacyAssignment:
    staff_id: str
    profile_id: str
    date: date
    shift_type_id: str


@dataclass
class ScheduleResult:
    assignments: list[LegacyAssignment]
    bad_sequences: int
    solver_status: str
    objective_value: int


def _config_to_spec(config: ScheduleConfig) -> ScheduleSpec:
    from packages.scheduler.spec import (
        OffRequestRule as _Off,
        ScheduleSpec as _Spec,
        SequenceRule as _Seq,
        ShiftDef as _Shift,
        ShiftSelector as _Sel,
        StaffMember as _Staff,
        WeeklyQuotaRule as _Quota,
    )

    shifts = [
        _Shift(
            id=st.id,
            label=st.code,
            start_min=st.start_hour * 60,
            end_min=1440 if st.end_hour == 0 else st.end_hour * 60,
            color_hex=st.color_hex,
            allowed_weekdays=[4, 5, 6] if st.weekend_only else None,
        )
        for st in config.shift_types
    ]
    rules: list = [
        _Quota(
            id="quota",
            description="Weekly shift quotas per duration",
            shifts_per_duration={float(q.duration_h): q.count_per_week for q in config.quota_rules},
            rest_days_per_week=0,
        ),
        _Seq(
            id="bad_sequence",
            description="Avoid close-at-midnight followed by early open",
            enforcement="soft",
            weight=100,
            mode="forbid",
            first=_Sel(ends_at_or_after_min=1440),
            second=_Sel(starts_at_or_before_min=480, max_duration_h=10),
        ),
    ]
    for i, (staff_id, dates) in enumerate(sorted(config.off_requests.items())):
        rules.append(_Off(id=f"off_{i}_{staff_id}", staff_id=staff_id, dates=sorted(dates)))

    return _Spec(
        start_date=config.start_date,
        num_days=config.num_days,
        staff=[_Staff(id=s.id, name=s.name) for s in config.staff],
        shifts=shifts,
        rules=rules,
        time_limit_seconds=config.time_limit_seconds,
    )


def solve(config: ScheduleConfig) -> ScheduleResult:
    """Legacy entry point — adapts the old dataclass config onto the spec
    engine. Raises RuntimeError when no schedule exists (old behaviour)."""
    spec = _config_to_spec(config)
    result = solve_with_relaxation(spec)
    if result.status == "infeasible":
        raise RuntimeError(f"No feasible schedule found. Solver status: {result.solver_status}")

    profile_by_staff = {s.id: s.profile_id for s in config.staff}
    assignments = [
        LegacyAssignment(
            staff_id=a.staff_id,
            profile_id=profile_by_staff[a.staff_id],
            date=a.date,
            shift_type_id=a.shift_id,
        )
        for a in result.assignments
        if a.shift_id != OFF
    ]
    return ScheduleResult(
        assignments=assignments,
        bad_sequences=result.violation_counts.get("bad_sequence", 0),
        solver_status=result.solver_status,
        objective_value=result.objective_value,
    )


# Old import name kept for backwards compatibility.
Assignment_legacy = LegacyAssignment
