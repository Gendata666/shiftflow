from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.core.ids import new_id

from app.core.database import get_db
from app.core.deps import require_manager, get_current_user
from app.core.security import hash_password
from app.models.user import User, StaffProfile, UserRole

router = APIRouter()


class StaffCreate(BaseModel):
    name: str
    email: EmailStr
    role_label: Optional[str] = None
    contract_hours: int = 40
    color: Optional[str] = None


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    role_label: Optional[str] = None
    contract_hours: Optional[int] = None
    color: Optional[str] = None
    active: Optional[bool] = None


@router.get("/")
async def list_staff(
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User, StaffProfile)
        .outerjoin(StaffProfile, StaffProfile.user_id == User.id)
        .where(User.tenant_id == manager.tenant_id)
        .order_by(User.name)
    )
    rows = result.all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "active": sp.active if sp else True,
            "contract_hours": sp.contract_hours if sp else 40,
            "role_label": sp.role_label if sp else None,
            "color": sp.color if sp else None,
            "profile_id": sp.id if sp else None,
        }
        for u, sp in rows
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_staff(
    body: StaffCreate,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(User).where(User.tenant_id == manager.tenant_id, User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists in this tenant")

    temp_password = new_id()[:12]
    user = User(
        id=new_id(),
        tenant_id=manager.tenant_id,
        email=body.email,
        name=body.name,
        password_hash=hash_password(temp_password),
        role=UserRole.STAFF,
    )
    db.add(user)
    await db.flush()

    profile = StaffProfile(
        id=new_id(),
        user_id=user.id,
        contract_hours=body.contract_hours,
        role_label=body.role_label,
        color=body.color,
    )
    db.add(profile)
    await db.commit()

    return {"id": user.id, "profile_id": profile.id, "temp_password": temp_password}


@router.patch("/{user_id}")
async def update_staff(
    user_id: str,
    body: StaffUpdate,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == manager.tenant_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Staff not found")

    if body.name:
        user.name = body.name

    profile_res = await db.execute(select(StaffProfile).where(StaffProfile.user_id == user_id))
    profile = profile_res.scalar_one_or_none()
    if profile:
        if body.role_label is not None:
            profile.role_label = body.role_label
        if body.contract_hours is not None:
            profile.contract_hours = body.contract_hours
        if body.color is not None:
            profile.color = body.color
        if body.active is not None:
            profile.active = body.active

    await db.commit()
    return {"ok": True}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff(
    user_id: str,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == manager.tenant_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Staff not found")
    await db.delete(user)
    await db.commit()
