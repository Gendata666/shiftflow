from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import date
from typing import Optional
import cuid2

from app.core.database import get_db
from app.core.deps import require_manager, get_current_user
from app.models.user import User
from app.models.preference import Preference, PrefSource, PrefType, PrefStatus
from app.core.timeutil import utcnow

router = APIRouter()


class PreferenceCreate(BaseModel):
    period_id: Optional[str] = None
    type: PrefType
    target_dates: list[str]
    notes: Optional[str] = None


@router.get("/")
async def list_preferences(
    period_id: Optional[str] = None,
    status_filter: Optional[PrefStatus] = None,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Preference, User)
        .join(User, User.id == Preference.staff_id)
        .where(User.tenant_id == manager.tenant_id)
    )
    if period_id:
        q = q.where(Preference.period_id == period_id)
    if status_filter:
        q = q.where(Preference.status == status_filter)

    result = await db.execute(q.order_by(Preference.created_at.desc()))
    rows = result.all()
    return [
        {
            "id": p.id,
            "staff_id": p.staff_id,
            "staff_name": u.name,
            "source": p.source,
            "type": p.type,
            "target_dates": p.target_dates,
            "raw_message": p.raw_message,
            "notes": p.notes,
            "status": p.status,
            "created_at": p.created_at,
        }
        for p, u in rows
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_preference(
    body: PreferenceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pref = Preference(
        id=cuid2.cuid(),
        staff_id=user.id,
        period_id=body.period_id,
        source=PrefSource.WEB,
        type=body.type,
        target_dates=body.target_dates,
        notes=body.notes,
    )
    db.add(pref)
    await db.commit()
    return {"id": pref.id}


@router.patch("/{pref_id}/approve")
async def approve_preference(
    pref_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Preference, User)
        .join(User, User.id == Preference.staff_id)
        .where(Preference.id == pref_id, User.tenant_id == manager.tenant_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Preference not found")

    from datetime import datetime
    pref, _ = row
    pref.status = PrefStatus.APPROVED
    pref.resolved_at = utcnow()
    pref.resolved_by = manager.id
    await db.commit()
    return {"ok": True}


@router.patch("/{pref_id}/reject")
async def reject_preference(
    pref_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Preference, User)
        .join(User, User.id == Preference.staff_id)
        .where(Preference.id == pref_id, User.tenant_id == manager.tenant_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Preference not found")

    from datetime import datetime
    pref, _ = row
    pref.status = PrefStatus.REJECTED
    pref.resolved_at = utcnow()
    pref.resolved_by = manager.id
    await db.commit()
    return {"ok": True}
