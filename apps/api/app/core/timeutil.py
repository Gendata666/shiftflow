"""Naive-UTC timestamps (DB columns are timezone-naive UTC)."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
