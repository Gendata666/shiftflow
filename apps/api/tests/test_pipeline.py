"""
Pipeline behaviour tests: infeasibility ladder (explicit relaxation reports,
never crashes), auto-repair escalation, and off-request handling.
"""

from datetime import date, timedelta

from packages.scheduler.orchestrator import generate
from packages.scheduler.spec import (
    OFF,
    CoverageRule,
    DaySelector,
    OffRequestRule,
    ScheduleSpec,
    ShiftDef,
    StaffMember,
    WeeklyQuotaRule,
)
from packages.scheduler.verifier import build_grid

MON = date(2026, 7, 6)

TWO_STAFF = [StaffMember(id="s1", name="One"), StaffMember(id="s2", name="Two")]
THREE_STAFF = TWO_STAFF + [StaffMember(id="s3", name="Three")]
DAY_SHIFTS = [
    ShiftDef(id="M", start_min=480, end_min=960),    # 08–16
    ShiftDef(id="N", start_min=960, end_min=1440),   # 16–00
]


def test_impossible_coverage_is_relaxed_and_reported():
    """3 staff cannot cover min 4 — the ladder must relax the rule and say so
    explicitly instead of failing (client brief rule 10)."""
    spec = ScheduleSpec(
        start_date=MON, num_days=7, staff=THREE_STAFF, shifts=DAY_SHIFTS,
        time_limit_seconds=10,
        rules=[
            CoverageRule(
                id="impossible", description="min 4 staff with only 3 hired",
                window_start_min=480, window_end_min=960, min_staff=4,
                relaxable=True,
            ),
        ],
    )
    report = generate(spec)
    assert report.result.status in ("optimal", "feasible")
    assert report.result.relaxed_rule_ids == ["impossible"]
    finding = next(f for f in report.findings if f.rule_id == "impossible")
    assert finding.status == "relaxed"
    assert finding.violations > 0
    assert finding.message_bg  # bilingual report present


def test_impossible_and_not_relaxable_reports_infeasible():
    spec = ScheduleSpec(
        start_date=MON, num_days=7, staff=THREE_STAFF, shifts=DAY_SHIFTS,
        time_limit_seconds=10,
        rules=[
            CoverageRule(
                id="impossible", description="min 4 staff with only 3 hired",
                window_start_min=480, window_end_min=960, min_staff=4,
            ),
        ],
    )
    report = generate(spec)
    assert report.result.status == "infeasible"
    assert report.findings == []  # honest: nothing to verify, no crash


def test_auto_repair_escalates_violated_soft_rule():
    """A cheap soft rule the optimum tramples gets escalated to hard by the
    orchestrator and holds after re-solve (client script #2, rule 7)."""
    spec = ScheduleSpec(
        start_date=MON, num_days=7, staff=TWO_STAFF, shifts=DAY_SHIFTS,
        time_limit_seconds=10,
        rules=[
            CoverageRule(
                id="morning_pull", description="wants both staff on mornings",
                enforcement="soft", weight=100,
                window_start_min=480, window_end_min=960, min_staff=2,
            ),
            CoverageRule(
                id="evening_min", description="someone must cover evenings",
                enforcement="soft", weight=1, auto_repair=True,
                window_start_min=960, window_end_min=1440, min_staff=1,
            ),
        ],
    )
    report = generate(spec)
    assert "evening_min" in report.escalated_rule_ids
    assert report.repair_iterations >= 1
    finding = next(f for f in report.findings if f.rule_id == "evening_min")
    assert finding.status == "ok"


def test_off_request_forces_rest_and_relaxes_quota():
    """An approved off-request forces OFF; that week's quota goes elastic
    (the old engine silently ignored off-requests — engine.py:151 `pass`)."""
    off_day = MON + timedelta(days=2)
    spec = ScheduleSpec(
        start_date=MON, num_days=7, staff=TWO_STAFF, shifts=DAY_SHIFTS,
        time_limit_seconds=10,
        rules=[
            WeeklyQuotaRule(
                id="quota", shifts_per_duration={8: 7}, rest_days_per_week=0,
                enforcement="hard",
            ),
            OffRequestRule(id="off_s1", staff_id="s1", dates=[off_day]),
        ],
    )
    report = generate(spec)
    assert report.result.status in ("optimal", "feasible")
    grid = build_grid(report.result.assignments)
    assert grid[("s1", off_day)] == OFF
    off_finding = next(f for f in report.findings if f.rule_id == "off_s1")
    assert off_finding.status == "ok"
    # s2 has no off-request: quota fully enforced — works all 7 days.
    assert all(grid[("s2", MON + timedelta(days=i))] != OFF for i in range(7))
