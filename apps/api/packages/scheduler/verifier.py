"""
ShiftFlow Verifier — independent, deterministic re-check of every spec rule
against a produced schedule. No solver, no AI: this is the proof layer the
client asked for ("направи проверка за всеки ден поотделно") and the test
oracle that keeps the engine honest.

Each rule type gets a _verify_* mirror of its engine handler. Findings carry
bilingual messages and cell references ("staff@YYYY-MM-DD") so the UI can
highlight offending cells.
"""

from __future__ import annotations

from datetime import date, timedelta

from packages.scheduler.spec import (
    OFF,
    Assignment,
    CoverageRule,
    DayShiftRestrictionRule,
    FairnessRule,
    Finding,
    OffRequestRule,
    ScheduleSpec,
    SequenceRule,
    StartSpreadRule,
    WeeklyQuotaRule,
)

Grid = dict[tuple[str, date], str]  # (staff_id, date) -> shift_id | OFF


def build_grid(assignments: list[Assignment]) -> Grid:
    return {(a.staff_id, a.date): a.shift_id for a in assignments}


def _cell(staff_id: str, d: date) -> str:
    return f"{staff_id}@{d.isoformat()}"


def _mk(rule, violations: int, cells: list[str], en: str, bg: str,
        relaxed: bool) -> Finding:
    if violations == 0:
        status = "ok"
        en, bg = "OK", "OK"
    else:
        status = "relaxed" if relaxed else "violated"
    return Finding(
        rule_id=rule.id, rule_type=rule.type, status=status,
        violations=violations, cells=cells[:50], message_en=en, message_bg=bg,
    )


# ─── Per-rule verifiers ───────────────────────────────────────────────────────

def _verify_weekly_quota(rule: WeeklyQuotaRule, spec: ScheduleSpec, grid: Grid, relaxed: bool) -> Finding:
    violations, cells, notes = 0, [], []
    scope = [s.id for s in spec.staff if rule.staff_ids is None or s.id in rule.staff_ids]
    forced_off: dict[str, set[date]] = {}
    for r in spec.rules:
        if isinstance(r, OffRequestRule) and r.enforcement == "hard":
            forced_off.setdefault(r.staff_id, set()).update(r.dates)

    for sid in scope:
        for w in range(spec.num_weeks()):
            day_idx = list(range(w * 7, min((w + 1) * 7, spec.num_days)))
            days = [spec.start_date + timedelta(days=i) for i in day_idx]
            full_week = len(days) == 7
            forced = len([d for d in days if d in forced_off.get(sid, set())])
            expected_off = min(rule.rest_days_per_week + forced, len(days))

            off_count = sum(1 for d in days if grid.get((sid, d)) == OFF)
            elastic = (not full_week) or forced > 0
            if (not elastic and off_count != expected_off) or (elastic and off_count > expected_off):
                violations += abs(off_count - expected_off)
                notes.append(f"{sid} W{w + 1}: OFF={off_count}≠{expected_off}")

            for dur, quota in rule.shifts_per_duration.items():
                count = sum(
                    1 for d in days
                    if (k := grid.get((sid, d))) not in (None, OFF)
                    and spec.shift_by_id(k).duration_h == dur
                )
                bad = (count != quota) if not elastic else (count > quota)
                if bad:
                    violations += abs(count - quota)
                    notes.append(f"{sid} W{w + 1}: {dur}h={count}≠{quota}")
                    cells.extend(_cell(sid, d) for d in days)

    detail = "; ".join(notes[:8])
    return _mk(rule, violations, cells,
               f"Weekly quota broken: {detail}",
               f"Нарушена седмична бройка смени: {detail}", relaxed)


def _verify_day_shift_restriction(rule: DayShiftRestrictionRule, spec: ScheduleSpec, grid: Grid, relaxed: bool) -> Finding:
    violations, cells = 0, []
    for d in spec.days():
        if not rule.days.matches(d):
            continue
        for s in spec.staff:
            k = grid.get((s.id, d))
            if k in (None, OFF):
                continue
            if not rule.allowed.matches(spec.shift_by_id(k)):
                violations += 1
                cells.append(_cell(s.id, d))
    return _mk(rule, violations, cells,
               f"{violations} assignment(s) use a shift not allowed on those days",
               f"{violations} смяна/и са в неразрешен за деня тип", relaxed)


def _presence_count(spec: ScheduleSpec, grid: Grid, d: date, hour: int) -> int:
    n = 0
    for s in spec.staff:
        k = grid.get((s.id, d))
        if k not in (None, OFF) and spec.shift_by_id(k).covers_hour(hour):
            n += 1
    return n


def _verify_coverage(rule: CoverageRule, spec: ScheduleSpec, grid: Grid, relaxed: bool) -> Finding:
    violations, cells, notes = 0, [], []
    for d in spec.days():
        if not rule.days.matches(d):
            continue
        for hour in rule.hours():
            present = _presence_count(spec, grid, d, hour)
            if rule.min_staff is not None and present < rule.min_staff:
                violations += rule.min_staff - present
                notes.append(f"{d.isoformat()} {hour:02d}h: {present}<{rule.min_staff}")
            if rule.max_staff is not None and present > rule.max_staff:
                violations += present - rule.max_staff
                notes.append(f"{d.isoformat()} {hour:02d}h: {present}>{rule.max_staff}")
    detail = "; ".join(notes[:8])
    return _mk(rule, violations, cells,
               f"Coverage broken: {detail}",
               f"Нарушено покритие: {detail}", relaxed)


def _verify_start_spread(rule: StartSpreadRule, spec: ScheduleSpec, grid: Grid, relaxed: bool) -> Finding:
    violations, cells, notes = 0, [], []
    for d in spec.days():
        if not rule.days.matches(d):
            continue
        starters = [
            s.id for s in spec.staff
            if (k := grid.get((s.id, d))) not in (None, OFF)
            and rule.window_start_min <= spec.shift_by_id(k).start_min < rule.window_end_min
        ]
        if len(starters) > rule.max_starts:
            violations += len(starters) - rule.max_starts
            notes.append(f"{d.isoformat()}: {len(starters)} starts")
            cells.extend(_cell(sid, d) for sid in starters)
    detail = "; ".join(notes[:8])
    return _mk(rule, violations, cells,
               f"Too many staff starting together: {detail}",
               f"Прекалено много служители започват едновременно: {detail}", relaxed)


def _verify_sequence(rule: SequenceRule, spec: ScheduleSpec, grid: Grid, relaxed: bool) -> Finding:
    first_ids = {s.id for s in spec.shifts if rule.first.matches(s)}
    second_ids = {s.id for s in spec.shifts if rule.second.matches(s)}
    scope = [s.id for s in spec.staff if rule.staff_ids is None or s.id in rule.staff_ids]
    days = spec.days()
    violations, cells = 0, []

    if rule.mode == "forbid":
        for sid in scope:
            for i in range(len(days) - 1):
                if grid.get((sid, days[i])) in first_ids and grid.get((sid, days[i + 1])) in second_ids:
                    violations += 1
                    cells += [_cell(sid, days[i]), _cell(sid, days[i + 1])]
        return _mk(rule, violations, cells,
                   f"Forbidden sequence occurs {violations} time(s)",
                   f"Нежеланата последователност се среща {violations} път/и", relaxed)

    weeks = rule.weeks if rule.weeks is not None else list(range(spec.num_weeks()))
    missing = []
    for sid in scope:
        for w in weeks:
            idx = list(range(w * 7, min((w + 1) * 7, spec.num_days)))
            found = any(
                grid.get((sid, days[i])) in first_ids and grid.get((sid, days[i + 1])) in second_ids
                for i in idx[:-1]
            )
            if not found:
                violations += 1
                missing.append(f"{sid} W{w + 1}")
    return _mk(rule, violations, cells,
               f"Required sequence missing for: {', '.join(missing)}",
               f"Изискваната последователност липсва за: {', '.join(missing)}", relaxed)


def _verify_fairness(rule: FairnessRule, spec: ScheduleSpec, grid: Grid, relaxed: bool) -> Finding:
    shift_ids = {s.id for s in spec.shifts if rule.shifts.matches(s)}
    scope = [s.id for s in spec.staff if rule.staff_ids is None or s.id in rule.staff_ids]
    if not shift_ids or len(scope) < 2:
        return _mk(rule, 0, [], "OK", "OK", relaxed)
    counts = {
        sid: sum(
            1 for d in spec.days()
            if rule.days.matches(d) and grid.get((sid, d)) in shift_ids
        )
        for sid in scope
    }
    spread = max(counts.values()) - min(counts.values())
    violations = max(0, spread - rule.max_spread)
    detail = ", ".join(f"{sid}={c}" for sid, c in counts.items())
    return _mk(rule, violations, [],
               f"Uneven distribution (spread {spread} > {rule.max_spread}): {detail}",
               f"Неравномерно разпределение (разлика {spread} > {rule.max_spread}): {detail}", relaxed)


def _verify_off_request(rule: OffRequestRule, spec: ScheduleSpec, grid: Grid, relaxed: bool) -> Finding:
    violations, cells = 0, []
    for dt in rule.dates:
        if not (spec.start_date <= dt < spec.start_date + timedelta(days=spec.num_days)):
            continue
        if grid.get((rule.staff_id, dt)) != OFF:
            violations += 1
            cells.append(_cell(rule.staff_id, dt))
    return _mk(rule, violations, cells,
               f"Approved off-request not honoured on {violations} day(s)",
               f"Одобрена заявка за почивка не е спазена в {violations} ден/дни", relaxed)


_VERIFIERS = {
    "weekly_quota": _verify_weekly_quota,
    "day_shift_restriction": _verify_day_shift_restriction,
    "coverage": _verify_coverage,
    "start_spread": _verify_start_spread,
    "sequence": _verify_sequence,
    "fairness": _verify_fairness,
    "off_request": _verify_off_request,
}


def verify(spec: ScheduleSpec, assignments: list[Assignment],
           relaxed_rule_ids: list[str] | None = None) -> list[Finding]:
    """Check every rule in the spec against the schedule. Rules the ladder
    relaxed are reported with status 'relaxed' (explicitly impossible to
    satisfy fully) rather than 'violated'."""
    relaxed = set(relaxed_rule_ids or [])
    grid = build_grid(assignments)
    return [
        _VERIFIERS[rule.type](rule, spec, grid, rule.id in relaxed)
        for rule in spec.rules
    ]
