"""
ShiftFlow Orchestrator — the solve → verify → auto-repair pipeline.

Implements client script #2, rule 7: after generating, audit every rule; if a
soft rule marked auto_repair is violated, escalate it to hard (but relaxable,
so a genuinely impossible rule ends up explicitly *relaxed and reported*
rather than looping forever) and re-solve. Bounded iterations; the final
report always states exactly which rules hold, which were relaxed as
mathematically impossible, and which are still violated.

Zero AI tokens are spent here — the whole loop is CP-SAT + deterministic
verification.
"""

from __future__ import annotations

from packages.scheduler.engine import solve_with_relaxation
from packages.scheduler.spec import Finding, GenerateReport, ScheduleSpec, SolveResult
from packages.scheduler.verifier import verify

MAX_REPAIR_ITERATIONS = 3


def generate(spec: ScheduleSpec, max_repair_iterations: int = MAX_REPAIR_ITERATIONS) -> GenerateReport:
    escalated: list[str] = []
    current = spec

    result: SolveResult | None = None
    findings: list[Finding] = []
    iterations = 0

    for iterations in range(max_repair_iterations + 1):
        result = solve_with_relaxation(current)
        if result.status == "infeasible":
            # Nothing left to relax — report honestly instead of crashing.
            return GenerateReport(
                result=result,
                findings=[],
                repair_iterations=iterations,
                escalated_rule_ids=escalated,
            )

        findings = verify(current, result.assignments, result.relaxed_rule_ids)

        to_escalate = [
            f.rule_id
            for f in findings
            if f.status == "violated"
            and (rule := current.rule_by_id(f.rule_id)).enforcement == "soft"
            and rule.auto_repair
        ]
        if not to_escalate:
            break

        # Escalate: soft → hard-but-relaxable, so an impossible rule is
        # explicitly relaxed and reported instead of looping.
        patched = current.model_copy(deep=True)
        for rule in patched.rules:
            if rule.id in to_escalate:
                rule.enforcement = "hard"
                rule.relaxable = True
        current = patched
        escalated.extend(to_escalate)

    return GenerateReport(
        result=result,
        findings=findings,
        repair_iterations=iterations,
        escalated_rule_ids=escalated,
    )
