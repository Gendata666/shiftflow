"""
In-memory OTP store for linking staff to bot accounts.
For production: replace with Redis (TTL keys).
"""

import random
import time
from typing import Optional

_store: dict[str, tuple[str, float]] = {}  # otp → (user_id, expires_at)
OTP_TTL = 600  # 10 minutes


def generate_otp(user_id: str) -> str:
    otp = f"{random.randint(100000, 999999)}"
    _store[otp] = (user_id, time.time() + OTP_TTL)
    return otp


def verify_otp(otp: str) -> Optional[str]:
    entry = _store.get(otp)
    if not entry:
        return None
    user_id, expires_at = entry
    if time.time() > expires_at:
        del _store[otp]
        return None
    del _store[otp]
    return user_id
