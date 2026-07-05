from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.core.ids import new_id

from app.core.database import get_db
from app.core.deps import require_manager
from app.models.user import User
from app.models.shift_type import ShiftType

router = APIRouter()


class ShiftTypeCreate(BaseModel):
    code: str
    label: str
    start_hour: int
    start_min: int = 0
    end_hour: int
    end_min: int = 0
    duration_h: int
    color_hex: str = "#B3D9FF"
    weekend_only: bool = False
    sort_order: int = 0


class ShiftTypeUpdate(BaseModel):
    label: Optional[str] = None
    color_hex: Optional[str] = None
    weekend_only: Optional[bool] = None
    active: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("/")
async def list_shift_types(
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShiftType)
        .where(ShiftType.tenant_id == manager.tenant_id, ShiftType.active == True)
        .order_by(ShiftType.sort_order, ShiftType.code)
    )
    rows = result.scalars().all()
    return [
        {
            "id": s.id,
            "code": s.code,
            "label": s.label,
            "start": f"{s.start_hour:02d}:{s.start_min:02d}",
            "end": f"{s.end_hour:02d}:{s.end_min:02d}",
            "duration_h": s.duration_h,
            "color_hex": s.color_hex,
            "weekend_only": s.weekend_only,
            "sort_order": s.sort_order,
        }
        for s in rows
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_shift_type(
    body: ShiftTypeCreate,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(ShiftType).where(ShiftType.tenant_id == manager.tenant_id, ShiftType.code == body.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Shift code '{body.code}' already exists")

    st = ShiftType(id=new_id(), tenant_id=manager.tenant_id, **body.model_dump())
    db.add(st)
    await db.commit()
    return {"id": st.id}


@router.patch("/{shift_type_id}")
async def update_shift_type(
    shift_type_id: str,
    body: ShiftTypeUpdate,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShiftType).where(ShiftType.id == shift_type_id, ShiftType.tenant_id == manager.tenant_id)
    )
    st = result.scalar_one_or_none()
    if not st:
        raise HTTPException(status_code=404, detail="Shift type not found")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(st, k, v)
    await db.commit()
    return {"ok": True}
