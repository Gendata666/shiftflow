from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import list


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DEBUG: bool = False
    SECRET_KEY: str
    DATABASE_URL: str
    ANTHROPIC_API_KEY: str

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_DAYS: int = 7

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""

    # Resend
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@digitalnebula.net"

    # Redis (optional for demo — falls back to in-process)
    REDIS_URL: str = ""


settings = Settings()
