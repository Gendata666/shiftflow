"""
Property-based tests: random small specs must never crash the pipeline, and
whenever the solver reports success without relaxation, the independent
verifier must agree that every hard rule holds. This is the engine↔verifier
consistency oracle.
"""

from datetime import date

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st  # noqa: E402

from packages.scheduler.orchestrator import generate  # noqa: E402
from packages.scheduler.spec import (  # noqa: E402
    CoverageRule,
    FairnessRule,
    ScheduleSpec,
    SequenceRule,
    ShiftDef,
    ShiftSelector,
    StaffMember,
    StartSpreadRule,
    WeeklyQuotaRule,
)

MON = date(2026, 7, 6)

# A small, sane shift catalog; strategies pick subsets of rules over it.
CATALOG = [
    ShiftDef(id="early", start_min=480, end_min=960),     # 08–16, 8h
    ShiftDef(id="mid", start_min=600, end_min=1200),      # 10–20, 10h
    ShiftDef(id="late", start_min=960, end_min=1440),     # 16–00, 8h
    ShiftDef(id="long", start_min=720, end_min=1440),     # 12–00, 12h
]


@st.composite
def specs(draw):
    n_staff = draw(st.integers(min_value=2, max_value=4))
    staff = [StaffMember(id=f"s{i}", name=f"S{i}") for i in range(n_staff)]
    rules = []

    if draw(st.booleans()):
        rules.append(WeeklyQuotaRule(
            id="quota",
            shifts_per_duration={8: draw(st.integers(0, 3)), 10: draw(st.integers(0, 2))},
            rest_days_per_week=draw(st.integers(0, 2)),
            enforcement=draw(st.sampled_from(["hard", "soft"])),
            relaxable=True, relax_priority=1,
        ))
    if draw(st.booleans()):
        rules.append(CoverageRule(
            id="cov",
            window_start_min=draw(st.sampled_from([480, 960, 1320])),
            window_end_min=1440,
            min_staff=draw(st.integers(1, n_staff + 1)),  # may exceed headcount
            enforcement=draw(st.sampled_from(["hard", "soft"])),
            relaxable=True, relax_priority=2,
        ))
    if draw(st.booleans()):
        rules.append(StartSpreadRule(
            id="spread", window_start_min=480, window_end_min=660,
            max_starts=draw(st.integers(0, n_staff)),
            enforcement="soft", weight=10, auto_repair=draw(st.booleans()),
        ))
    if draw(st.booleans()):
        rules.append(FairnessRule(
            id="fair", shifts=ShiftSelector(ends_at_or_after_min=1440),
            max_spread=draw(st.integers(0, 2)), enforcement="soft", weight=5,
        ))
    if draw(st.booleans()):
        rules.append(SequenceRule(
            id="seq", mode="forbid",
            first=ShiftSelector(ends_at_or_after_min=1440),
            second=ShiftSelector(starts_at_or_before_min=480),
            enforcement=draw(st.sampled_from(["hard", "soft"])),
            relaxable=True, relax_priority=3,
        ))

    return ScheduleSpec(
        start_date=MON, num_days=draw(st.sampled_from([7, 10, 14])),
        staff=staff, shifts=CATALOG, rules=rules, time_limit_seconds=5,
    )


@settings(max_examples=25, deadline=None)
@given(specs())
def test_pipeline_never_crashes_and_is_self_consistent(spec):
    report = generate(spec)

    if report.result.status == "infeasible":
        # Honest failure is allowed only when nothing was relaxable.
        assert not any(
            r.enforcement == "hard" and r.relaxable for r in spec.rules
        ) or report.result.relaxed_rule_ids
        return

    # Every staff-day has exactly one assignment.
    assert len(report.result.assignments) == len(spec.staff) * spec.num_days

    # Engine and verifier must agree: hard, unrelaxed rules show status ok.
    relaxed = set(report.result.relaxed_rule_ids)
    escalated = set(report.escalated_rule_ids)
    for f in report.findings:
        rule = spec.rule_by_id(f.rule_id)
        if rule.enforcement == "hard" and f.rule_id not in relaxed | escalated:
            assert f.status == "ok", (
                f"hard rule {f.rule_id} violated but solver said OK: {f.message_en}"
            )
