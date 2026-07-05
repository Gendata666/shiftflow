"""
Manager copilot — the only place ShiftFlow spends AI tokens.

Provider-switchable (settings.LLM_PROVIDER):
  * "gemini"    — pilot default: gemini-3.5-flash on the free tier
                  (~10 RPM / 1,500 req/day — zero cost)
  * "anthropic" — Claude Opus 4.8 for production quality

Two entry points, identical contracts on both providers:
  * parse_brief / parse_brief_update — one structured-outputs call turning a
    natural-language brief (BG/EN) into a SpecDraft or SpecUpdateDraft. The
    result is converted and re-validated deterministically (spec_draft.py);
    the manager confirms the interpretation before anything is solved.
  * CopilotSession.send — a streaming tool-use loop for conversational work.
    The model never sees the schedule grid: tools return compact spec JSON,
    verification summaries and per-staff stats computed in Python. Solving
    and verification cost zero tokens on any provider.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import AsyncIterator, Awaitable, Callable, Optional

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.spec_draft import SpecDraft, SpecUpdateDraft, apply_update, min_to_hhmm
from app.services.solver_runner import generate_async
from packages.scheduler.spec import OFF, GenerateReport, ScheduleSpec

COPILOT_MODEL = "claude-opus-4-8"

_client: Optional[AsyncAnthropic] = None


def _use_gemini() -> bool:
    return settings.LLM_PROVIDER.lower() == "gemini"


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ─── Shared vocabulary primer (kept byte-stable for prompt caching) ──────────

VOCABULARY_PRIMER = """\
You translate shift-scheduling requirements into ShiftFlow's constraint vocabulary.
You NEVER produce schedules — a CP-SAT solver does that. You produce rules.

Conventions:
- Times are "HH:MM" 24h strings. "00:00" as an END time means midnight.
- Weekdays: Mon=0 Tue=1 Wed=2 Thu=3 Fri=4 Sat=5 Sun=6. In Bulgarian venues
  "уикенд" typically means Fri+Sat+Sun = [4,5,6] — follow the brief.
- Rule enforcement mapping from natural language:
  * "задължително", "никога", "не допускай"          → enforcement=hard
  * "максимално да се избягва", "по възможност"       → enforcement=soft (weight 50–200 by emphasis)
  * "ако е математически невъзможно — възможно
     най-рядко / най-близко"                          → hard + relaxable=true
  * "провери след генерирането и преработи, докато
     правилата бъдат спазени"                         → auto_repair=true on those rules
- Rule types:
  * weekly_quota          — exact per-week shift counts per duration + rest days
  * day_shift_restriction — on selected days only certain shifts are allowed
  * coverage              — min/max staff present during a time window
                            ("никой не затваря сам" → min_staff=2 on the closing window;
                             "покритие през целия ден" → min_staff=1 open→close)
  * start_spread          — max N staff starting within a start-time window
                            ("не всички първа смяна" → max 2 starting 08:00–10:00)
  * sequence forbid       — consecutive-day pattern to avoid (e.g. 16:00–00:00
                            then 08:00–16:00 next day)
  * sequence require      — pattern that MUST occur (per staff, per week)
  * fairness              — matching shifts spread evenly across staff
  * off_request           — approved day off for one person
- Shifts the brief calls preferred/main get preferred=true; "могат да се
  използват при нужда" get preferred=false.
- Give every rule a short snake_case id and a one-line description in the
  brief's language. List every assumption you had to make.
"""

PARSE_NEW_SYSTEM = VOCABULARY_PRIMER + """
Task: read the manager's brief and produce the COMPLETE SpecDraft: staff,
shift catalog, and every rule the brief states or clearly implies. Do not
invent rules the brief doesn't support.
"""

PARSE_UPDATE_SYSTEM = VOCABULARY_PRIMER + """
Task: the manager sent a FOLLOW-UP brief for an existing spec (provided as
JSON). Client rules are cumulative: produce only the DIFF (SpecUpdateDraft) —
add/replace/remove shifts and rules. Never restate unchanged rules. Use
replace_rules only for rule ids that already exist. If a "new" shift already
exists in the catalog (check ids and times), use replace_shifts to modify it
(e.g. promote a fallback shift to preferred=true) — never add_shifts a
duplicate.
"""


async def parse_brief(text: str, start_date, num_days: int, staff_hint: str = "") -> SpecDraft:
    """One structured-outputs call: brief → SpecDraft."""
    user = (
        f"Schedule horizon: start {start_date.isoformat()}, {num_days} days.\n"
        + (f"Known staff: {staff_hint}\n" if staff_hint else "")
        + f"\nManager brief:\n{text}"
    )
    if _use_gemini():
        from app.services.gemini_llm import parse_structured
        return await parse_structured(PARSE_NEW_SYSTEM, user, SpecDraft)

    response = await _get_client().messages.parse(
        model=COPILOT_MODEL,
        max_tokens=16000,
        system=[{"type": "text", "text": PARSE_NEW_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=SpecDraft,
    )
    return response.parsed_output


async def parse_brief_update(text: str, current_spec: ScheduleSpec) -> SpecUpdateDraft:
    """One structured-outputs call: follow-up brief + current spec → diff."""
    user = (
        f"Current spec JSON:\n{current_spec.model_dump_json()}\n\n"
        f"Manager follow-up brief:\n{text}"
    )
    if _use_gemini():
        from app.services.gemini_llm import parse_structured
        return await parse_structured(PARSE_UPDATE_SYSTEM, user, SpecUpdateDraft)

    response = await _get_client().messages.parse(
        model=COPILOT_MODEL,
        max_tokens=16000,
        system=[{"type": "text", "text": PARSE_UPDATE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=SpecUpdateDraft,
    )
    return response.parsed_output


# ─── Deterministic summaries (what the model/UI sees instead of the grid) ────

def report_summary(spec: ScheduleSpec, report: GenerateReport) -> dict:
    """Compact, token-cheap summary of a solve: statuses, findings, per-staff
    stats. This — not the 112-cell grid — is what the copilot reads."""
    per_staff: dict[str, dict] = {}
    for member in spec.staff:
        rows = [a for a in report.result.assignments if a.staff_id == member.id]
        shift_counts = Counter(a.shift_id for a in rows)
        late = sum(
            1 for a in rows
            if a.shift_id != OFF and spec.shift_by_id(a.shift_id).end_min >= 1440
        )
        weekend_late = sum(
            1 for a in rows
            if a.shift_id != OFF
            and a.date.weekday() in (4, 5, 6)
            and spec.shift_by_id(a.shift_id).end_min >= 1440
        )
        per_staff[member.name] = {
            "shifts": dict(shift_counts),
            "closing_shifts": late,
            "weekend_closings": weekend_late,
            "days_off": shift_counts.get(OFF, 0),
        }

    return {
        "status": report.result.status,
        "solver_status": report.result.solver_status,
        "clean": report.clean,
        "repair_iterations": report.repair_iterations,
        "escalated_rules": report.escalated_rule_ids,
        "relaxed_rules_impossible_to_fully_satisfy": report.result.relaxed_rule_ids,
        "findings": [
            {
                "rule": f.rule_id, "status": f.status, "violations": f.violations,
                "detail": f.message_bg or f.message_en,
            }
            for f in report.findings
        ],
        "per_staff": per_staff,
    }


def spec_overview(spec: ScheduleSpec) -> dict:
    """Compact spec view for the model — shifts as clock times, rules as
    one-liners."""
    return {
        "version": spec.version,
        "venue": spec.venue_name,
        "horizon": {"start": spec.start_date.isoformat(), "days": spec.num_days},
        "staff": [{"id": s.id, "name": s.name} for s in spec.staff],
        "shifts": [
            {
                "id": s.id,
                "time": f"{min_to_hhmm(s.start_min)}–{min_to_hhmm(s.end_min)}",
                "hours": s.duration_h,
                "preferred": s.preferred,
                "days": s.allowed_weekdays,
            }
            for s in spec.shifts
        ],
        "rules": [
            {
                "id": r.id, "type": r.type, "enforcement": r.enforcement,
                "auto_repair": r.auto_repair, "relaxable": r.relaxable,
                "description": r.description,
            }
            for r in spec.rules
        ],
    }


# ─── Conversational copilot (streaming tool loop) ────────────────────────────

CHAT_SYSTEM = VOCABULARY_PRIMER + """
You are ShiftFlow's scheduling copilot talking to the venue manager. Answer
in the manager's language (Bulgarian or English).

Ground rules:
- You never write schedules yourself. Use the tools: read the spec, apply
  confirmed rule changes, generate, and read the verification summary.
- Rule changes: state your interpretation of the requested change and apply
  it with apply_spec_update; report exactly what changed.
- After generate_schedule, report from the verification summary: what holds,
  what was impossible (relaxed rules) and how often it is violated. Never
  claim a rule holds without the summary saying so.
- Questions like "why does X always close?" are answered from per-staff
  stats in the summary, not by guessing.
- Be concise and concrete.
"""

CHAT_TOOLS = [
    {
        "name": "get_spec",
        "description": "Read the current schedule spec (staff, shift catalog, all rules) as compact JSON.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "apply_spec_update",
        "description": (
            "Apply a confirmed change to the spec: add/replace/remove shifts and rules. "
            "Input follows the SpecUpdateDraft schema (times as HH:MM strings). "
            "Returns the new spec version or a validation error."
        ),
        "input_schema": SpecUpdateDraft.model_json_schema(),
    },
    {
        "name": "generate_schedule",
        "description": (
            "Run the constraint solver on the current spec (takes seconds, costs nothing). "
            "Returns a verification summary: rule findings, relaxed/impossible rules, per-staff stats."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_verification_report",
        "description": "Re-read the verification summary of the most recent generated schedule.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


class CopilotSession:
    """One manager chat session bound to a spec. The host (router) supplies
    persistence callbacks; this class owns the model loop."""

    def __init__(
        self,
        spec: ScheduleSpec,
        history: Optional[list[dict]] = None,
        on_spec_change: Optional[Callable[[ScheduleSpec], Awaitable[None]]] = None,
        on_report: Optional[Callable[[GenerateReport], Awaitable[None]]] = None,
    ):
        self.spec = spec
        self.history: list[dict] = history or []
        self.last_report: Optional[GenerateReport] = None
        self._on_spec_change = on_spec_change
        self._on_report = on_report

    async def _run_tool(self, name: str, tool_input: dict) -> str:
        if name == "get_spec":
            return json.dumps(spec_overview(self.spec), ensure_ascii=False)

        if name == "apply_spec_update":
            try:
                update = SpecUpdateDraft.model_validate(tool_input)
                self.spec = apply_update(self.spec, update)
            except Exception as e:  # validation must fail loudly but inside the loop
                return json.dumps({"error": str(e)}, ensure_ascii=False)
            if self._on_spec_change:
                await self._on_spec_change(self.spec)
            return json.dumps(
                {"ok": True, "new_version": self.spec.version, "summary": update.summary_bg},
                ensure_ascii=False,
            )

        if name == "generate_schedule":
            self.last_report = await generate_async(self.spec)
            if self._on_report:
                await self._on_report(self.last_report)
            return json.dumps(report_summary(self.spec, self.last_report), ensure_ascii=False)

        if name == "get_verification_report":
            if self.last_report is None:
                return json.dumps({"error": "no schedule generated yet"})
            return json.dumps(report_summary(self.spec, self.last_report), ensure_ascii=False)

        return json.dumps({"error": f"unknown tool {name}"})

    async def send(self, user_message: str) -> AsyncIterator[dict]:
        """Stream one manager turn. Yields SSE-ready events:
        {"type": "text", "text"} | {"type": "tool", "name"} |
        {"type": "spec_updated", "version"} | {"type": "report", "summary"} |
        {"type": "done"}."""
        if _use_gemini():
            async for event in self._send_gemini(user_message):
                yield event
            return
        async for event in self._send_claude(user_message):
            yield event

    async def _send_gemini(self, user_message: str) -> AsyncIterator[dict]:
        from app.services.gemini_llm import stream_chat_turn

        spec_version_before = self.spec.version
        report_before = self.last_report

        async for event in stream_chat_turn(
            system=CHAT_SYSTEM,
            history=self.history,  # google.genai Content objects for gemini sessions
            user_message=user_message,
            chat_tools=CHAT_TOOLS,
            run_tool=self._run_tool,
        ):
            if event.get("type") == "tool_done":
                # Internal marker — translate into side-effect events.
                if event["name"] == "apply_spec_update" and self.spec.version != spec_version_before:
                    spec_version_before = self.spec.version
                    yield {"type": "spec_updated", "version": self.spec.version}
                elif event["name"] == "generate_schedule" and self.last_report is not report_before:
                    report_before = self.last_report
                    yield {"type": "report", "summary": report_summary(self.spec, self.last_report)}
                continue
            yield event

    async def _send_claude(self, user_message: str) -> AsyncIterator[dict]:
        client = _get_client()
        self.history.append({"role": "user", "content": user_message})

        while True:
            async with client.messages.stream(
                model=COPILOT_MODEL,
                max_tokens=16000,
                system=[{"type": "text", "text": CHAT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=CHAT_TOOLS,
                messages=self.history,
            ) as stream:
                async for text in stream.text_stream:
                    yield {"type": "text", "text": text}
                response = await stream.get_final_message()

            self.history.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                yield {"type": "tool", "name": block.name}
                result = await self._run_tool(block.name, block.input or {})
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )
                if block.name == "apply_spec_update":
                    yield {"type": "spec_updated", "version": self.spec.version}
                elif block.name == "generate_schedule" and self.last_report is not None:
                    yield {"type": "report", "summary": report_summary(self.spec, self.last_report)}
            self.history.append({"role": "user", "content": tool_results})

        yield {"type": "done"}
