"""
Golden acceptance tests — the two real client briefs, expressed as
ScheduleSpecs and asserted end-to-end through solve → verify.

Brief #1: the original 28-day beach-bar script (quotas, weekend 12h rule,
two closers, fairness rotation, forbidden BAD sequence, reward sequences).

Brief #2: the client's feedback script (hourly coverage curves, never close
alone, start-time spread, late-shift fairness, new shifts) — the two ❌
examples from the delivered xlsx must be impossible here.
"""

from datetime import date, timedelta

import pytest

from packages.scheduler.orchestrator import generate
from packages.scheduler.spec import (
    OFF,
    CoverageRule,
    DayShiftRestrictionRule,
    DaySelector,
    FairnessRule,
    ScheduleSpec,
    SequenceRule,
    ShiftDef,
    ShiftSelector,
    StaffMember,
    StartSpreadRule,
    WeeklyQuotaRule,
    WEEKEND,
    WEEKDAYS,
)
from packages.scheduler.verifier import build_grid

START = date(2026, 7, 6)  # Monday
STAFF = [
    StaffMember(id="vasil", name="Васил"),
    StaffMember(id="niki", name="Ники"),
    StaffMember(id="dzhedaya", name="Джедая"),
    StaffMember(id="afrodita", name="Афродита"),
]

# Shift catalog from brief #1 (preferred + fallback 8h shifts); colors match
# the delivered beach_bar_grafik.xlsx legend (8h blue, 10h amber, 12h green/salmon)
SHIFTS_V1 = [
    ShiftDef(id="A", start_min=480, end_min=960, color_hex="#B3D9FF"),                    # 08–16, 8h
    ShiftDef(id="B", start_min=960, end_min=1440, color_hex="#B3D9FF"),                   # 16–00, 8h
    ShiftDef(id="A2", start_min=840, end_min=1320, preferred=False, color_hex="#B3D9FF"), # 14–22, 8h fallback
    ShiftDef(id="A3", start_min=600, end_min=1080, preferred=False, color_hex="#B3D9FF"), # 10–18, 8h fallback
    ShiftDef(id="C", start_min=600, end_min=1200, color_hex="#FFD580"),                   # 10–20, 10h
    ShiftDef(id="D", start_min=840, end_min=1440, color_hex="#FFD580"),                   # 14–00, 10h
    ShiftDef(id="E", start_min=480, end_min=1200, allowed_weekdays=WEEKEND, color_hex="#90EE90"),  # 08–20, 12h
    ShiftDef(id="F", start_min=720, end_min=1440, allowed_weekdays=WEEKEND, color_hex="#FFA07A"),  # 12–00, 12h
]

REWARD_WEEKS = {"dzhedaya": 0, "vasil": 1, "niki": 2, "afrodita": 3}


def brief1_rules():
    rules = [
        WeeklyQuotaRule(
            id="quota", description="2×8h + 2×10h + 3×12h per week, no rest days",
            shifts_per_duration={8: 2, 10: 2, 12: 3}, rest_days_per_week=0,
        ),
        DayShiftRestrictionRule(
            id="weekend_12h_only", description="Fri/Sat/Sun everyone works 12h shifts",
            days=DaySelector(weekdays=WEEKEND),
            allowed=ShiftSelector(min_duration_h=12),
        ),
        CoverageRule(
            id="two_closers_weekend", description="Exactly two close at 00:00 on Fri/Sat/Sun",
            days=DaySelector(weekdays=WEEKEND),
            window_start_min=1200, window_end_min=1440, min_staff=2, max_staff=2,
        ),
        FairnessRule(
            id="closing_rotation", description="Weekend closing role rotates fairly",
            enforcement="soft", weight=50,
            shifts=ShiftSelector(shift_ids=["F"]),
            days=DaySelector(weekdays=WEEKEND), max_spread=1,
        ),
        SequenceRule(
            id="bad_sequence", description="Avoid 16–00 followed by early open next day",
            enforcement="soft", weight=100, mode="forbid",
            first=ShiftSelector(ends_at_or_after_min=1440),
            second=ShiftSelector(starts_at_or_before_min=480, max_duration_h=10),
        ),
    ]
    for staff_id, week in REWARD_WEEKS.items():
        rules.append(SequenceRule(
            id=f"reward_{staff_id}", description=f"08–16 then 16–00 in week {week + 1}",
            mode="require", staff_ids=[staff_id], weeks=[week],
            first=ShiftSelector(shift_ids=["A"]),
            second=ShiftSelector(shift_ids=["B"]),
        ))
    return rules


def make_spec_v1() -> ScheduleSpec:
    return ScheduleSpec(
        venue_name="Beach Bar", start_date=START, num_days=28,
        staff=STAFF, shifts=SHIFTS_V1, rules=brief1_rules(),
        time_limit_seconds=60,
    )


@pytest.fixture(scope="module")
def report_v1():
    return generate(make_spec_v1())


class TestBrief1:
    def test_solves_without_relaxation(self, report_v1):
        assert report_v1.result.status in ("optimal", "feasible")
        assert report_v1.result.relaxed_rule_ids == []

    def test_verifier_clean(self, report_v1):
        bad = [f for f in report_v1.findings if f.status != "ok"]
        assert bad == [], [f"{f.rule_id}: {f.message_en}" for f in bad]

    def test_everyone_works_every_day(self, report_v1):
        grid = build_grid(report_v1.result.assignments)
        for s in STAFF:
            for i in range(28):
                assert grid[(s.id, START + timedelta(days=i))] != OFF

    def test_zero_bad_sequences(self, report_v1):
        assert report_v1.result.violation_counts.get("bad_sequence", 0) == 0

    def test_weekend_two_closers(self, report_v1):
        grid = build_grid(report_v1.result.assignments)
        for i in range(28):
            d = START + timedelta(days=i)
            if d.weekday() in WEEKEND:
                closers = [s.id for s in STAFF if grid[(s.id, d)] == "F"]
                assert len(closers) == 2, f"{d}: {closers}"

    def test_reward_sequences(self, report_v1):
        grid = build_grid(report_v1.result.assignments)
        for staff_id, week in REWARD_WEEKS.items():
            found = any(
                grid[(staff_id, START + timedelta(days=d))] == "A"
                and grid[(staff_id, START + timedelta(days=d + 1))] == "B"
                for d in range(week * 7, week * 7 + 6)
            )
            assert found, f"{staff_id} missing A→B in week {week + 1}"


# ─── Brief #2: the feedback script ───────────────────────────────────────────

SHIFTS_V2 = [s for s in SHIFTS_V1 if s.id != "A3"] + [
    ShiftDef(id="G", start_min=480, end_min=1080, color_hex="#FFD580"),   # 08–18, 10h (new, "use actively")
    ShiftDef(id="H", start_min=600, end_min=1080, color_hex="#B3D9FF"),   # 10–18, 8h (new — replaces fallback A3)
    ShiftDef(id="I", start_min=540, end_min=1140, color_hex="#FFD580"),   # 09–19, 10h
    ShiftDef(id="J", start_min=720, end_min=1320, color_hex="#FFD580"),   # 12–22, 10h
]


def brief2_rules():
    rules = brief1_rules()
    rules += [
        CoverageRule(
            id="never_close_alone", description="≥2 present during the closing window",
            days=DaySelector(weekdays=WEEKDAYS),
            window_start_min=1320, window_end_min=1440, min_staff=2,
        ),
        CoverageRule(
            id="all_day_coverage", description="Someone present from open to close",
            days=DaySelector(weekdays=WEEKDAYS),
            window_start_min=480, window_end_min=1440, min_staff=1,
        ),
        StartSpreadRule(
            id="start_spread", description="No pile-up on first shift (max 2 early starts)",
            days=DaySelector(weekdays=WEEKDAYS),
            window_start_min=480, window_end_min=600, max_starts=2,
        ),
        FairnessRule(
            id="late_shift_fairness", description="Closing shifts spread evenly",
            enforcement="soft", weight=50, auto_repair=True,
            shifts=ShiftSelector(ends_at_or_after_min=1440), max_spread=2,
        ),
    ]
    return rules


def make_spec_v2() -> ScheduleSpec:
    return ScheduleSpec(
        venue_name="Beach Bar", start_date=START, num_days=28,
        staff=STAFF, shifts=SHIFTS_V2, rules=brief2_rules(),
        time_limit_seconds=90,
    )


@pytest.fixture(scope="module")
def report_v2():
    return generate(make_spec_v2())


class TestBrief2:
    def test_solves(self, report_v2):
        assert report_v2.result.status in ("optimal", "feasible")
        assert report_v2.result.relaxed_rule_ids == []

    def test_verifier_clean(self, report_v2):
        bad = [f for f in report_v2.findings if f.status != "ok"]
        assert bad == [], [f"{f.rule_id}: {f.message_en}" for f in bad]

    def test_no_lone_closer(self, report_v2):
        """❌ Week 1 Tuesday in the delivered xlsx: one person alone until
        midnight. Must be impossible now."""
        spec = make_spec_v2()
        grid = build_grid(report_v2.result.assignments)
        for i in range(28):
            d = START + timedelta(days=i)
            for hour in (22, 23):
                present = sum(
                    1 for s in STAFF
                    if grid[(s.id, d)] != OFF
                    and spec.shift_by_id(grid[(s.id, d)]).covers_hour(hour)
                )
                assert present >= 2, f"{d} {hour}:00 — only {present} present"

    def test_no_first_shift_pileup(self, report_v2):
        """❌ Week 4 Monday in the delivered xlsx: everyone on first shift.
        Must be impossible now."""
        spec = make_spec_v2()
        grid = build_grid(report_v2.result.assignments)
        for i in range(28):
            d = START + timedelta(days=i)
            if d.weekday() not in WEEKDAYS:
                continue
            early = [
                s.id for s in STAFF
                if grid[(s.id, d)] != OFF
                and spec.shift_by_id(grid[(s.id, d)]).start_min < 600
            ]
            assert len(early) <= 2, f"{d}: {len(early)} early starters {early}"

    def test_late_shifts_fair(self, report_v2):
        spec = make_spec_v2()
        grid = build_grid(report_v2.result.assignments)
        late_counts = {
            s.id: sum(
                1 for i in range(28)
                if grid[(s.id, START + timedelta(days=i))] != OFF
                and spec.shift_by_id(grid[(s.id, START + timedelta(days=i))]).end_min >= 1440
            )
            for s in STAFF
        }
        spread = max(late_counts.values()) - min(late_counts.values())
        assert spread <= 2, late_counts


def test_spec_json_roundtrip():
    """The AI contract: a spec must survive JSON serialisation unchanged."""
    spec = make_spec_v2()
    restored = ScheduleSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec
