"""Test bootstrap: provide the required settings before any `app.*` import
so unit tests never need a real database or API key."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DEBUG", "true")
