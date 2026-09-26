"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import auth as admin_auth
from app.api.admin import catalog as admin_catalog
from app.api.admin import commerce as admin_commerce
from app.api.admin import content as admin_content
from app.api.checkout import router as checkout_router
from app.api.payments import router as payments_router
from app.api.public import router as public_router
from app.core.config import settings
from app.core.errors import register_error_handlers

logging.basicConfig(level=logging.INFO)

_INSECURE_DEFAULT_SECRET = "dev-only-insecure-secret-change-me"

if settings.is_production and settings.secret_key == _INSECURE_DEFAULT_SECRET:
    raise RuntimeError("SECRET_KEY must be set to a real value in production.")

app = FastAPI(
    title="Retro Watches API",
    version="0.1.0",
    # No interactive docs in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Explicit origins only, and credentials are on because admin auth is a cookie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

register_error_handlers(app)

app.include_router(public_router)
app.include_router(checkout_router)
app.include_router(payments_router)
app.include_router(admin_auth.router)
app.include_router(admin_catalog.router)
app.include_router(admin_commerce.router)
app.include_router(admin_content.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
