from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.core.ids import new_id

from app.core.database import get_db
from app.core.deps import require_manager
from app.models.user import User
from app.models.venue import Venue

router = APIRouter()


class VenueCreate(BaseModel):
    name: str
    timezone: str = "Europe/Sofia"


@router.get("/")
async def list_venues(manager: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Venue).where(Venue.tenant_id == manager.tenant_id, Venue.active == True)
    )
    return [{"id": v.id, "name": v.name, "timezone": v.timezone} for v in result.scalars().all()]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_venue(
    body: VenueCreate,
    manager: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    venue = Venue(id=new_id(), tenant_id=manager.tenant_id, **body.model_dump())
    db.add(venue)
    await db.commit()
    return {"id": venue.id}
