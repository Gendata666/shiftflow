"""
Bot webhook handlers — Telegram (more bots added in Phase 2)
Staff link their account via a 6-digit OTP shown in the dashboard.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.ids import new_id

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, StaffProfile
from app.models.preference import Preference, PrefSource, PrefType, PrefStatus
from app.services.preference_parser import parse_preference_message
from app.services.otp import verify_otp, generate_otp

router = APIRouter()


# ─── OTP linking ─────────────────────────────────────────────────────────────

@router.post("/telegram/otp")
async def get_link_otp(user: User = Depends(get_current_user)):
    """Generate a 6-digit OTP for the *authenticated* staff member to link
    their Telegram account. The identity comes from the JWT — accepting an
    arbitrary user_id here would let anyone hijack any account's bot link."""
    otp = generate_otp(user.id)
    return {"otp": otp, "expires_in": 600}


# ─── Telegram webhook ─────────────────────────────────────────────────────────

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    # Verify secret token from Telegram
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if settings.TELEGRAM_WEBHOOK_SECRET and secret != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    body = await request.json()
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = str(message["chat"]["id"])
    text = message.get("text", "").strip()

    # Check if staff linked this chat_id
    result = await db.execute(
        select(User, StaffProfile)
        .join(StaffProfile, StaffProfile.user_id == User.id)
        .where(StaffProfile.bot_chat_ids["telegram"].as_string() == chat_id)
    )
    row = result.first()

    # Handle /start with OTP
    if text.startswith("/start"):
        parts = text.split()
        if len(parts) > 1:
            otp = parts[1]
            user_id = verify_otp(otp)
            if user_id:
                user_res = await db.execute(
                    select(User, StaffProfile)
                    .outerjoin(StaffProfile, StaffProfile.user_id == User.id)
                    .where(User.id == user_id)
                )
                user_row = user_res.first()
                if user_row:
                    user, profile = user_row
                    if profile:
                        bot_ids = profile.bot_chat_ids or {}
                        bot_ids["telegram"] = chat_id
                        profile.bot_chat_ids = bot_ids
                        await db.commit()
                        await _send_telegram(chat_id, f"Свързано! Здравей, {user.name} 👋\nМожеш да ми изпращаш заявки за смени.")
                        return {"ok": True}
            await _send_telegram(chat_id, "Невалиден или изтекъл код. Генерирай нов от приложението.")
        else:
            await _send_telegram(chat_id, "Използвай линка от приложението за свързване на акаунт.")
        return {"ok": True}

    if not row:
        await _send_telegram(chat_id, "Акаунтът ти не е свързан. Използвай линка от приложението.")
        return {"ok": True}

    user, profile = row

    # Parse preference via Claude Haiku
    parsed = await parse_preference_message(text, user.name)
    if not parsed:
        await _send_telegram(chat_id, "Не разбрах съобщението. Опитай: 'Не мога в петък 18 юли' или 'Предпочитам ранна смяна тази неделя'.")
        return {"ok": True}

    # Store preference
    pref = Preference(
        id=new_id(),
        staff_id=user.id,
        source=PrefSource.TELEGRAM,
        type=PrefType(parsed["type"]),
        target_dates=parsed.get("dates", []),
        raw_message=text,
        parsed_json=parsed,
        notes=parsed.get("notes"),
    )
    db.add(pref)
    await db.commit()

    # Confirm to user
    dates_str = ", ".join(parsed.get("dates", [])) or "неизвестни дати"
    type_labels = {
        "OFF_REQUEST": "Заявка за почивка",
        "UNAVAILABLE": "Недостъпен",
        "PREFERRED_SHIFT": "Предпочитана смяна",
        "NOTES": "Бележка",
    }
    label = type_labels.get(parsed["type"], parsed["type"])
    await _send_telegram(
        chat_id,
        f"Записах: {label} за {dates_str}\nМениджърът ще прегледа и потвърди заявката."
    )
    return {"ok": True}


async def _send_telegram(chat_id: str, text: str):
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    import httpx
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
