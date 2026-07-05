"""
Copilot API — spec lifecycle + streaming manager chat.

Flow mirroring how the real client iterated:
  1. POST /specs/parse           brief → interpreted spec (DRAFT) + summary + assumptions
  2. POST /specs/{id}/confirm    manager approves the interpretation → ACTIVE
  3. POST /specs/{id}/update     follow-up brief → diff, applied as new version (DRAFT)
  4. POST /specs/{id}/generate   solver runs off the event loop; report stored
  5. POST /chat                  SSE tool-use chat bound to a spec
"""

from __future__ import annotations

import json
from datetime import date

from app.core.ids import new_id
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.core.deps import require_manager
from app.models.spec import RunStatus, ScheduleRun, SpecRecord, SpecStatus
from app.models.user import User
from app.services import copilot
from app.services.solver_runner import generate_async
from app.services.spec_draft import apply_update
from packages.scheduler.spec import GenerateReport, ScheduleSpec

router = APIRouter()


class ParseBriefRequest(BaseModel):
    brief: str
    start_date: date
    num_days: int
    venue_id: str | None = None
    staff_hint: str = ""


class UpdateBriefRequest(BaseModel):
    brief: str


class ChatRequest(BaseModel):
    spec_id: str
    message: str


async def _load_spec_record(spec_id: str, tenant_id: str, db: AsyncSession) -> SpecRecord:
    res = await db.execute(
        select(SpecRecord).where(SpecRecord.id == spec_id, SpecRecord.tenant_id == tenant_id)
    )
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Spec not found")
    return record


def _spec_payload(record: SpecRecord) -> dict:
    spec = ScheduleSpec.model_validate_json(record.spec_json)
    return {
        "id": record.id,
        "version": record.version,
        "status": record.status,
        "summary": record.summary,
        "overview": copilot.spec_overview(spec),
        "spec": spec.model_dump(mode="json"),
    }


@router.post("/specs/parse", status_code=201)
async def parse_brief(
    body: ParseBriefRequest,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Brief → interpreted DRAFT spec. The manager must confirm before use."""
    draft = await copilot.parse_brief(body.brief, body.start_date, body.num_days, body.staff_hint)
    try:
        spec = draft.to_spec()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Interpreted spec failed validation: {e}")

    record = SpecRecord(
        id=new_id(),
        tenant_id=manager.tenant_id,
        venue_id=body.venue_id,
        version=spec.version,
        status=SpecStatus.DRAFT,
        spec_json=spec.model_dump_json(),
        source_brief=body.brief,
        summary=draft.summary_bg,
        created_by=manager.id,
    )
    db.add(record)
    await db.commit()
    payload = _spec_payload(record)
    payload["assumptions"] = draft.assumptions
    return payload


@router.post("/specs/{spec_id}/confirm")
async def confirm_spec(
    spec_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    record = await _load_spec_record(spec_id, manager.tenant_id, db)
    record.status = SpecStatus.ACTIVE
    await db.commit()
    return {"ok": True, "status": record.status}


@router.post("/specs/{spec_id}/update", status_code=201)
async def update_from_brief(
    spec_id: str,
    body: UpdateBriefRequest,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Follow-up brief → diff onto the current spec → new DRAFT version
    (rules are cumulative; prior rules persist unless explicitly changed)."""
    record = await _load_spec_record(spec_id, manager.tenant_id, db)
    spec = ScheduleSpec.model_validate_json(record.spec_json)

    update = await copilot.parse_brief_update(body.brief, spec)
    try:
        new_spec = apply_update(spec, update)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Diff failed to apply: {e}")

    new_record = SpecRecord(
        id=new_id(),
        tenant_id=manager.tenant_id,
        venue_id=record.venue_id,
        version=new_spec.version,
        status=SpecStatus.DRAFT,
        spec_json=new_spec.model_dump_json(),
        source_brief=body.brief,
        summary=update.summary_bg,
        created_by=manager.id,
    )
    db.add(new_record)
    await db.commit()
    payload = _spec_payload(new_record)
    payload["assumptions"] = update.assumptions
    payload["previous_spec_id"] = record.id
    return payload


@router.get("/specs/{spec_id}")
async def get_spec(
    spec_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    record = await _load_spec_record(spec_id, manager.tenant_id, db)
    return _spec_payload(record)


@router.post("/specs/{spec_id}/generate", status_code=201)
async def generate_schedule(
    spec_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Run the solver (off the event loop) and store the full report."""
    record = await _load_spec_record(spec_id, manager.tenant_id, db)
    spec = ScheduleSpec.model_validate_json(record.spec_json)

    run = ScheduleRun(id=new_id(), tenant_id=manager.tenant_id, spec_id=spec_id)
    db.add(run)
    await db.commit()

    try:
        report = await generate_async(spec)
    except Exception as e:
        run.status = RunStatus.ERROR
        run.error = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Solver error: {e}")

    run.status = RunStatus.INFEASIBLE if report.result.status == "infeasible" else RunStatus.DONE
    run.report_json = report.model_dump_json()
    await db.commit()

    return {
        "run_id": run.id,
        "status": run.status,
        "summary": copilot.report_summary(spec, report),
        "assignments": [a.model_dump(mode="json") for a in report.result.assignments],
    }


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(ScheduleRun).where(ScheduleRun.id == run_id, ScheduleRun.tenant_id == manager.tenant_id)
    )
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    report = GenerateReport.model_validate_json(run.report_json) if run.report_json else None
    spec_record = await _load_spec_record(run.spec_id, manager.tenant_id, db)
    spec = ScheduleSpec.model_validate_json(spec_record.spec_json)
    return {
        "id": run.id,
        "status": run.status,
        "error": run.error,
        "summary": copilot.report_summary(spec, report) if report else None,
        "assignments": [a.model_dump(mode="json") for a in report.result.assignments] if report else [],
        "findings": [f.model_dump() for f in report.findings] if report else [],
    }


async def _load_run_with_spec(run_id: str, tenant_id: str, db: AsyncSession):
    res = await db.execute(
        select(ScheduleRun).where(ScheduleRun.id == run_id, ScheduleRun.tenant_id == tenant_id)
    )
    run = res.scalar_one_or_none()
    if not run or not run.report_json:
        raise HTTPException(status_code=404, detail="Run not found or has no report")
    spec_record = await _load_spec_record(run.spec_id, tenant_id, db)
    spec = ScheduleSpec.model_validate_json(spec_record.spec_json)
    report = GenerateReport.model_validate_json(run.report_json)
    return spec, report


@router.get("/runs/{run_id}/export.xlsx")
async def export_run_xlsx(
    run_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    from app.services.render_xlsx import render_xlsx

    spec, report = await _load_run_with_spec(run_id, manager.tenant_id, db)
    data = render_xlsx(spec, report)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="grafik_{run_id}.xlsx"'},
    )


@router.get("/runs/{run_id}/export.pdf")
async def export_run_pdf(
    run_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    from app.services.render_pdf import render_pdf

    spec, report = await _load_run_with_spec(run_id, manager.tenant_id, db)
    data = render_pdf(spec, report)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="grafik_{run_id}.pdf"'},
    )


@router.post("/chat")
async def chat(
    body: ChatRequest,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """One manager chat turn, streamed as SSE. Spec changes made by the
    copilot's tools are persisted as new spec versions."""
    record = await _load_spec_record(body.spec_id, manager.tenant_id, db)
    spec = ScheduleSpec.model_validate_json(record.spec_json)
    tenant_id, created_by, venue_id = manager.tenant_id, manager.id, record.venue_id

    async def persist_spec(new_spec: ScheduleSpec) -> None:
        async with AsyncSessionLocal() as session:
            session.add(SpecRecord(
                id=new_id(), tenant_id=tenant_id, venue_id=venue_id,
                version=new_spec.version, status=SpecStatus.ACTIVE,
                spec_json=new_spec.model_dump_json(),
                summary="updated via copilot chat", created_by=created_by,
            ))
            await session.commit()

    async def persist_report(report: GenerateReport) -> None:
        async with AsyncSessionLocal() as session:
            session.add(ScheduleRun(
                id=new_id(), tenant_id=tenant_id, spec_id=body.spec_id,
                status=RunStatus.INFEASIBLE if report.result.status == "infeasible" else RunStatus.DONE,
                report_json=report.model_dump_json(),
            ))
            await session.commit()

    session_obj = copilot.CopilotSession(
        spec, on_spec_change=persist_spec, on_report=persist_report
    )

    async def event_stream():
        async for event in session_obj.send(body.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
