from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import date
from app.core.ids import new_id

from app.core.database import get_db
from app.core.deps import require_manager
from app.models.user import User, StaffProfile
from app.models.schedule import Schedule, SchedulePeriod, ShiftAssignment, PeriodStatus
from app.models.shift_type import ShiftType
from app.models.preference import Preference, PrefStatus, PrefType
from app.core.timeutil import utcnow

router = APIRouter()


class PeriodCreate(BaseModel):
    venue_id: str
    label: str
    start_date: date
    end_date: date


class GenerateRequest(BaseModel):
    period_id: str
    time_limit_seconds: int = 30


@router.post("/periods", status_code=status.HTTP_201_CREATED)
async def create_period(
    body: PeriodCreate,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    period = SchedulePeriod(
        id=new_id(),
        tenant_id=manager.tenant_id,
        venue_id=body.venue_id,
        label=body.label,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(period)
    await db.commit()
    return {"id": period.id}


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_schedule(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    period_res = await db.execute(
        select(SchedulePeriod).where(
            SchedulePeriod.id == body.period_id,
            SchedulePeriod.tenant_id == manager.tenant_id,
        )
    )
    period = period_res.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    schedule = Schedule(
        id=new_id(),
        tenant_id=manager.tenant_id,
        venue_id=period.venue_id,
        period_id=period.id,
    )
    db.add(schedule)
    await db.commit()

    background_tasks.add_task(
        _run_solver,
        schedule_id=schedule.id,
        tenant_id=manager.tenant_id,
        period=period,
        time_limit=body.time_limit_seconds,
    )
    return {"schedule_id": schedule.id, "status": "generating"}


async def _run_solver(schedule_id: str, tenant_id: str, period: SchedulePeriod, time_limit: int):
    from app.core.database import AsyncSessionLocal
    from packages.scheduler.engine import solve, ScheduleConfig, ShiftTypeDef, StaffDef, QuotaRule
    from datetime import timedelta

    async with AsyncSessionLocal() as db:
        # Load shift types
        st_res = await db.execute(
            select(ShiftType).where(ShiftType.tenant_id == tenant_id, ShiftType.active == True)
        )
        shift_types = st_res.scalars().all()

        # Load active staff with profiles
        sp_res = await db.execute(
            select(User, StaffProfile)
            .join(StaffProfile, StaffProfile.user_id == User.id)
            .where(User.tenant_id == tenant_id, StaffProfile.active == True)
        )
        staff_rows = sp_res.all()

        # Load approved off requests
        off_res = await db.execute(
            select(Preference).where(
                Preference.period_id == period.id,
                Preference.status == PrefStatus.APPROVED,
                Preference.type == PrefType.OFF_REQUEST,
            )
        )
        prefs = off_res.scalars().all()
        off_requests: dict[str, set] = {}
        for pref in prefs:
            dates = set()
            for d in (pref.target_dates or []):
                if isinstance(d, str):
                    from datetime import date as date_cls
                    dates.add(date_cls.fromisoformat(d))
                else:
                    dates.add(d)
            off_requests[pref.staff_id] = off_requests.get(pref.staff_id, set()) | dates

        config = ScheduleConfig(
            staff=[StaffDef(id=u.id, name=u.name, profile_id=sp.id) for u, sp in staff_rows],
            shift_types=[
                ShiftTypeDef(
                    id=st.id,
                    code=st.code,
                    start_hour=st.start_hour,
                    end_hour=st.end_hour,
                    duration_h=st.duration_h,
                    weekend_only=st.weekend_only,
                    color_hex=st.color_hex,
                )
                for st in shift_types
            ],
            start_date=period.start_date,
            num_days=(period.end_date - period.start_date).days + 1,
            quota_rules=[
                QuotaRule(duration_h=8,  count_per_week=2),
                QuotaRule(duration_h=10, count_per_week=2),
                QuotaRule(duration_h=12, count_per_week=3),
            ],
            off_requests=off_requests,
            time_limit_seconds=time_limit,
        )

        try:
            # CP-SAT is CPU-bound — run it in the worker pool so the event
            # loop keeps serving requests during the solve.
            import asyncio
            from app.services.solver_runner import _get_pool
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(_get_pool(), solve, config)
        except RuntimeError as e:
            # Store error in schedule notes
            sched_res = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
            sched = sched_res.scalar_one()
            sched.notes = f"ERROR: {e}"
            await db.commit()
            return

        # Persist assignments
        for a in result.assignments:
            db.add(ShiftAssignment(
                id=new_id(),
                schedule_id=schedule_id,
                staff_id=a.profile_id,
                date=a.date,
                shift_type_id=a.shift_type_id,
            ))

        sched_res = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        sched = sched_res.scalar_one()
        sched.notes = f"BAD sequences: {result.bad_sequences} | solver: {result.solver_status}"
        await db.commit()


@router.get("/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Schedule).where(Schedule.id == schedule_id, Schedule.tenant_id == manager.tenant_id)
    )
    sched = result.scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    assignments_res = await db.execute(
        select(ShiftAssignment).where(ShiftAssignment.schedule_id == schedule_id)
    )
    assignments = assignments_res.scalars().all()

    return {
        "id": sched.id,
        "period_id": sched.period_id,
        "generated_at": sched.generated_at,
        "published_at": sched.published_at,
        "notes": sched.notes,
        "assignments": [
            {
                "id": a.id,
                "staff_profile_id": a.staff_id,
                "date": a.date.isoformat(),
                "shift_type_id": a.shift_type_id,
                "is_manual": a.is_manual,
            }
            for a in assignments
        ],
    }


@router.post("/{schedule_id}/publish")
async def publish_schedule(
    schedule_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    result = await db.execute(
        select(Schedule).where(Schedule.id == schedule_id, Schedule.tenant_id == manager.tenant_id)
    )
    sched = result.scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    sched.published_at = utcnow()
    period_res = await db.execute(select(SchedulePeriod).where(SchedulePeriod.id == sched.period_id))
    period = period_res.scalar_one()
    period.status = PeriodStatus.PUBLISHED
    await db.commit()
    return {"ok": True}
