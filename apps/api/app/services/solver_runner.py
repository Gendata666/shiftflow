"""
Run the CP-SAT pipeline off the event loop. CP-SAT is CPU-bound; running it
inline (or via FastAPI BackgroundTasks) freezes every other request. Specs
and reports cross the process boundary as JSON strings so nothing
unpicklable leaks through.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor

from packages.scheduler.orchestrator import generate
from packages.scheduler.spec import GenerateReport, ScheduleSpec

_pool: ProcessPoolExecutor | None = None


def _get_pool() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=2)
    return _pool


def _generate_json(spec_json: str) -> str:
    spec = ScheduleSpec.model_validate_json(spec_json)
    return generate(spec).model_dump_json()


async def generate_async(spec: ScheduleSpec) -> GenerateReport:
    loop = asyncio.get_running_loop()
    report_json = await loop.run_in_executor(_get_pool(), _generate_json, spec.model_dump_json())
    return GenerateReport.model_validate_json(report_json)


def shutdown_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None
