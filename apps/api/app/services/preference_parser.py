"""
AI preference parser using Claude Haiku.
Converts free-text staff messages → structured preference JSON.
Falls back to None if parsing fails.
"""

import json
from typing import Optional
from anthropic import AsyncAnthropic

from app.core.config import settings

_client: Optional[AsyncAnthropic] = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You extract work schedule preferences from staff messages.
Return ONLY a JSON object with these fields:
- type: one of "OFF_REQUEST", "UNAVAILABLE", "PREFERRED_SHIFT", "NOTES"
- dates: array of ISO date strings (YYYY-MM-DD). Infer from context; leave empty if unclear.
- shift_preference: "morning", "evening", "any", or null
- notes: short English summary of what was requested

If you cannot parse a preference, return {"type": null}.
Never add explanation outside the JSON."""


async def parse_preference_message(text: str, staff_name: str) -> Optional[dict]:
    try:
        client = _get_client()
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Staff member: {staff_name}\nMessage: {text}"}
            ],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        if not parsed.get("type"):
            return None
        return parsed
    except Exception:
        return None
