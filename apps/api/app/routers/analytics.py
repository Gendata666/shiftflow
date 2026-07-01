from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date

from app.core.database import get_db
from app.core.deps import require_manager
from app.models.user import User, StaffProfile
from app.models.schedule import Schedule, ShiftAssignment
from app.models.shift_type import ShiftType

router = APIRouter()


@router.get("/hours/{schedule_id}")
async def hours_report(
    schedule_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Return per-staff hours summary for a schedule."""
    result = await db.execute(
        select(
            User.id,
            User.name,
            ShiftType.duration_h,
            func.count(ShiftAssignment.id).label("count"),
        )
        .join(StaffProfile, StaffProfile.id == ShiftAssignment.staff_id)
        .join(User, User.id == StaffProfile.user_id)
        .join(ShiftType, ShiftType.id == ShiftAssignment.shift_type_id)
        .where(
            ShiftAssignment.schedule_id == schedule_id,
            User.tenant_id == manager.tenant_id,
        )
        .group_by(User.id, User.name, ShiftType.duration_h)
        .order_by(User.name)
    )
    rows = result.all()

    # Group by staff
    staff_map: dict[str, dict] = {}
    for user_id, name, duration_h, count in rows:
        if user_id not in staff_map:
            staff_map[user_id] = {"id": user_id, "name": name, "total_hours": 0, "shifts_by_duration": {}, "days_worked": 0}
        staff_map[user_id]["shifts_by_duration"][duration_h] = count
        staff_map[user_id]["total_hours"] += duration_h * count
        staff_map[user_id]["days_worked"] += count

    return list(staff_map.values())


@router.get("/weekly/{schedule_id}")
async def weekly_report(
    schedule_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Return per-staff weekly hours breakdown."""
    result = await db.execute(
        select(User.id, User.name, ShiftAssignment.date, ShiftType.duration_h)
        .join(StaffProfile, StaffProfile.id == ShiftAssignment.staff_id)
        .join(User, User.id == StaffProfile.user_id)
        .join(ShiftType, ShiftType.id == ShiftAssignment.shift_type_id)
        .where(ShiftAssignment.schedule_id == schedule_id, User.tenant_id == manager.tenant_id)
        .order_by(User.name, ShiftAssignment.date)
    )
    rows = result.all()

    # Group by staff → week
    staff_weeks: dict[str, dict] = {}
    for user_id, name, assign_date, duration_h in rows:
        if user_id not in staff_weeks:
            staff_weeks[user_id] = {"id": user_id, "name": name, "weeks": {}}
        if isinstance(assign_date, date):
            iso = assign_date.isocalendar()
            week_key = f"W{iso.week}"
        else:
            week_key = "W?"
        staff_weeks[user_id]["weeks"].setdefault(week_key, 0)
        staff_weeks[user_id]["weeks"][week_key] += duration_h

    return list(staff_weeks.values())
