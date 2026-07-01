from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.routers import auth, staff, venues, shift_types, schedules, preferences, export, analytics, bots


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect DB, register Telegram webhook
    from app.core.database import engine
    yield
    # Shutdown: cleanup
    await engine.dispose()


app = FastAPI(
    title="ShiftFlow API",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,        prefix="/api/auth",        tags=["auth"])
app.include_router(staff.router,       prefix="/api/staff",       tags=["staff"])
app.include_router(venues.router,      prefix="/api/venues",      tags=["venues"])
app.include_router(shift_types.router, prefix="/api/shift-types", tags=["shift-types"])
app.include_router(schedules.router,   prefix="/api/schedules",   tags=["schedules"])
app.include_router(preferences.router, prefix="/api/preferences", tags=["preferences"])
app.include_router(export.router,      prefix="/api/export",      tags=["export"])
app.include_router(analytics.router,   prefix="/api/analytics",   tags=["analytics"])
app.include_router(bots.router,        prefix="/api/bots",        tags=["bots"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
