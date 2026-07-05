"""
Tests for the deterministic halves of the copilot: draft→spec conversion,
diff application (client script #2 modelled as a SpecUpdateDraft), report
summaries, and the chat tool executor — no API calls, no tokens.
"""

import json
from datetime import date

import pytest

from app.services.copilot import CopilotSession, report_summary, spec_overview
from app.services.spec_draft import (
    CoverageDraft,
    QuotaCountDraft,
    SelectorDraft,
    ShiftDraft,
    SpecDraft,
    SpecUpdateDraft,
    StartSpreadDraft,
    WeeklyQuotaDraft,
    apply_update,
    hhmm_to_min,
)
from packages.scheduler.orchestrator import generate
from packages.scheduler.spec import DaySelector, ScheduleSpec, StaffMember

MON = date(2026, 7, 6)


def test_hhmm_conversion():
    assert hhmm_to_min("08:00") == 480
    assert hhmm_to_min("00:00", is_end=True) == 1440
    assert hhmm_to_min("00:00") == 0
    with pytest.raises(ValueError):
        hhmm_to_min("25:00")


def make_draft() -> SpecDraft:
    return SpecDraft(
        venue_name="Bar",
        start_date=MON,
        num_days=7,
        staff=[StaffMember(id="s1", name="One"), StaffMember(id="s2", name="Two")],
        shifts=[
            ShiftDraft(id="A", start="08:00", end="16:00"),
            ShiftDraft(id="B", start="16:00", end="00:00"),
            ShiftDraft(id="E", start="08:00", end="20:00", allowed_weekdays=[4, 5, 6]),
        ],
        rules=[
            WeeklyQuotaDraft(
                id="quota",
                quotas=[QuotaCountDraft(duration_h=8, count_per_week=5)],
                rest_days_per_week=2,
            ),
            CoverageDraft(
                id="close_min", window_start="22:00", window_end="00:00", min_staff=1,
                days=DaySelector(weekdays=[0, 1, 2, 3]),
            ),
        ],
        summary_bg="тест",
    )


def test_draft_to_spec_conversion():
    spec = make_draft().to_spec()
    assert isinstance(spec, ScheduleSpec)
    b = spec.shift_by_id("B")
    assert (b.start_min, b.end_min) == (960, 1440)  # "00:00" end = midnight
    assert spec.shift_by_id("E").allowed_weekdays == [4, 5, 6]
    quota = spec.rule_by_id("quota")
    assert quota.shifts_per_duration == {8: 5}
    cov = spec.rule_by_id("close_min")
    assert (cov.window_start_min, cov.window_end_min) == (1320, 1440)


def test_apply_update_is_cumulative_and_versioned():
    """Client script #2 pattern: new shifts + new rules merge in, old rules persist."""
    spec = make_draft().to_spec()
    update = SpecUpdateDraft(
        add_shifts=[ShiftDraft(id="G", start="08:00", end="18:00")],
        add_rules=[
            StartSpreadDraft(
                id="start_spread", window_start="08:00", window_end="10:00", max_starts=1,
            ),
        ],
        replace_rules=[
            CoverageDraft(
                id="close_min", window_start="22:00", window_end="00:00", min_staff=2,
                days=DaySelector(weekdays=[0, 1, 2, 3]),
            ),
        ],
        summary_bg="добавени нови смени и правила",
    )
    new_spec = apply_update(spec, update)

    assert new_spec.version == spec.version + 1
    assert {s.id for s in new_spec.shifts} == {"A", "B", "E", "G"}
    assert new_spec.rule_by_id("quota") == spec.rule_by_id("quota")  # untouched rule persists
    assert new_spec.rule_by_id("close_min").min_staff == 2           # replaced
    assert new_spec.rule_by_id("start_spread").max_starts == 1       # added
    # original untouched (immutability)
    assert spec.rule_by_id("close_min").min_staff == 1


def test_apply_update_fails_loudly_on_bad_ids():
    spec = make_draft().to_spec()
    with pytest.raises(ValueError, match="already exists"):
        apply_update(spec, SpecUpdateDraft(add_shifts=[ShiftDraft(id="A", start="09:00", end="17:00")]))
    with pytest.raises(ValueError, match="no rule with id"):
        apply_update(spec, SpecUpdateDraft(replace_rules=[
            CoverageDraft(id="ghost", window_start="08:00", window_end="10:00", min_staff=1),
        ]))


def test_report_summary_is_compact_and_grounded():
    spec = make_draft().to_spec()
    report = generate(spec)
    summary = report_summary(spec, report)

    assert summary["status"] in ("optimal", "feasible")
    assert set(summary["per_staff"].keys()) == {"One", "Two"}
    for stats in summary["per_staff"].values():
        assert stats["days_off"] == 2  # rest_days_per_week honoured
    # the summary must stay token-cheap — no 112-cell grids inside
    assert len(json.dumps(summary)) < 4000


@pytest.mark.asyncio
async def test_chat_tools_execute_against_spec():
    """The tool executor works without any AI: get_spec → apply update →
    generate → report, all deterministic."""
    session = CopilotSession(make_draft().to_spec())

    overview = json.loads(await session._run_tool("get_spec", {}))
    assert overview["version"] == 1
    assert {s["id"] for s in overview["shifts"]} == {"A", "B", "E"}

    update_input = SpecUpdateDraft(
        add_rules=[
            StartSpreadDraft(id="spread", window_start="08:00", window_end="10:00", max_starts=1),
        ],
        summary_bg="ограничение на ранните начала",
    ).model_dump(mode="json")
    result = json.loads(await session._run_tool("apply_spec_update", update_input))
    assert result["ok"] and result["new_version"] == 2

    bad = json.loads(await session._run_tool("apply_spec_update", {"add_rules": [{"type": "nope"}]}))
    assert "error" in bad  # hallucinated tool input fails inside the loop, not as a crash

    report = json.loads(await session._run_tool("generate_schedule", {}))
    assert report["status"] in ("optimal", "feasible")
    reread = json.loads(await session._run_tool("get_verification_report", {}))
    assert reread["status"] == report["status"]


def test_spec_overview_uses_clock_times():
    overview = spec_overview(make_draft().to_spec())
    times = {s["time"] for s in overview["shifts"]}
    assert "16:00–00:00" in times
