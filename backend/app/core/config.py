"""Environment-driven configuration. Nothing secret is ever hardcoded here."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "staging", "production"] = "development"

    # PostgreSQL in staging/production. SQLite is allowed in development only so the
    # project runs without a local Postgres install (see docs/DECISIONS.md).
    database_url: str = "sqlite:///./obaidi_time.db"

    # Signs the admin session cookie. Rotating it invalidates every session.
    secret_key: str = "dev-only-insecure-secret-change-me"

    # NoDecode: the value is a plain comma-separated string, not JSON.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    session_cookie_name: str = "obaidi_admin_session"
    session_max_age_seconds: int = 60 * 60 * 8
    session_cookie_secure: bool = False

    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300

    # Seed-only credentials; the runtime never reads ADMIN_PASSWORD after seeding.
    admin_email: str = "admin@retrowatches.jo"
    admin_password: str = "ChangeMe!Dev1"

    # Phase 4 wires a real provider behind app/payments. Nothing is charged yet.
    payment_provider: str = "unconfigured"
    payment_secret_key: str = ""
    payment_webhook_secret: str = ""

    # Where the payment provider sends the customer back to.
    storefront_url: str = "http://localhost:3000"

    default_currency: str = "USD"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
