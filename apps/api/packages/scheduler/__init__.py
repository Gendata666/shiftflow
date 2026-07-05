# Spec-driven engine (v2)
from packages.scheduler.spec import (  # noqa: F401
    OFF,
    Assignment,
    CoverageRule,
    DayShiftRestrictionRule,
    DaySelector,
    FairnessRule,
    Finding,
    GenerateReport,
    OffRequestRule,
    Rule,
    ScheduleSpec,
    SequenceRule,
    ShiftDef,
    ShiftSelector,
    SolveResult,
    StaffMember,
    StartSpreadRule,
    WeeklyQuotaRule,
)
from packages.scheduler.engine import solve_spec, solve_with_relaxation  # noqa: F401
from packages.scheduler.orchestrator import generate  # noqa: F401
from packages.scheduler.verifier import verify  # noqa: F401

# Legacy dataclass API (kept for the existing router/tests)
from packages.scheduler.engine import (  # noqa: F401
    QuotaRule,
    ScheduleConfig,
    ScheduleResult,
    ShiftTypeDef,
    StaffDef,
    solve,
)
