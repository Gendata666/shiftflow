"""
Scheduler engine unit tests.
Verifies constraint satisfaction without any database or API calls.
"""

import pytest
from datetime import date
from packages.scheduler.engine import (
    solve, ScheduleConfig, ShiftTypeDef, StaffDef, QuotaRule,
)


# Beach bar shift types from gen_grafik.py
BEACH_SHIFTS = [
    ShiftTypeDef(id="A", code="A", start_hour=8,  end_hour=16, duration_h=8,  weekend_only=False, color_hex="#B3D9FF"),
    ShiftTypeDef(id="B", code="B", start_hour=16, end_hour=0,  duration_h=8,  weekend_only=False, color_hex="#B3D9FF"),
    ShiftTypeDef(id="C", code="C", start_hour=10, end_hour=20, duration_h=10, weekend_only=False, color_hex="#FFD580"),
    ShiftTypeDef(id="D", code="D", start_hour=14, end_hour=0,  duration_h=10, weekend_only=False, color_hex="#FFD580"),
    ShiftTypeDef(id="E", code="E", start_hour=8,  end_hour=20, duration_h=12, weekend_only=True,  color_hex="#90EE90"),
    ShiftTypeDef(id="F", code="F", start_hour=12, end_hour=0,  duration_h=12, weekend_only=True,  color_hex="#FFA07A"),
]

BEACH_STAFF = [
    StaffDef(id="vasil",    name="Васил",    profile_id="p1"),
    StaffDef(id="niki",     name="Ники",     profile_id="p2"),
    StaffDef(id="dzhedaya", name="Джедая",   profile_id="p3"),
    StaffDef(id="afrodita", name="Афродита", profile_id="p4"),
]

BEACH_QUOTAS = [
    QuotaRule(duration_h=8,  count_per_week=2),
    QuotaRule(duration_h=10, count_per_week=2),
    QuotaRule(duration_h=12, count_per_week=3),
]


@pytest.fixture(scope="module")
def beach_result():
    config = ScheduleConfig(
        staff=BEACH_STAFF,
        shift_types=BEACH_SHIFTS,
        start_date=date(2026, 7, 6),  # Monday
        num_days=28,
        quota_rules=BEACH_QUOTAS,
        time_limit_seconds=60,
    )
    return solve(config)


def test_feasible(beach_result):
    assert beach_result.solver_status in ("OPTIMAL", "FEASIBLE")


def test_one_shift_per_person_per_day(beach_result):
    seen: dict[tuple, int] = {}
    for a in beach_result.assignments:
        key = (a.staff_id, a.date)
        seen[key] = seen.get(key, 0) + 1
    for key, count in seen.items():
        assert count == 1, f"Staff {key[0]} has {count} shifts on {key[1]}"


def test_weekly_quotas(beach_result):
    from datetime import timedelta
    start = date(2026, 7, 6)
    shift_dur = {s.id: s.duration_h for s in BEACH_SHIFTS}
    for staff in BEACH_STAFF:
        staff_assigns = [a for a in beach_result.assignments if a.staff_id == staff.id]
        for w in range(4):
            week_start = start + timedelta(weeks=w)
            week_end = week_start + timedelta(days=6)
            week = [a for a in staff_assigns if week_start <= a.date <= week_end]
            dur_counts = {}
            for a in week:
                d = shift_dur[a.shift_type_id]
                dur_counts[d] = dur_counts.get(d, 0) + 1
            assert dur_counts.get(8, 0) == 2, f"{staff.name} W{w+1}: 8h={dur_counts.get(8,0)}"
            assert dur_counts.get(10, 0) == 2, f"{staff.name} W{w+1}: 10h={dur_counts.get(10,0)}"
            assert dur_counts.get(12, 0) == 3, f"{staff.name} W{w+1}: 12h={dur_counts.get(12,0)}"


def test_weekend_only_on_weekends(beach_result):
    weekend_only_ids = {s.id for s in BEACH_SHIFTS if s.weekend_only}
    for a in beach_result.assignments:
        if a.shift_type_id in weekend_only_ids:
            assert a.date.weekday() >= 4, f"Weekend shift {a.shift_type_id} on {a.date} (weekday {a.date.weekday()})"


def test_zero_bad_sequences(beach_result):
    assert beach_result.bad_sequences == 0, f"Expected 0 BAD sequences, got {beach_result.bad_sequences}"
