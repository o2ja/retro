"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
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

logger = logging.getLogger("obaidi")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema and default admin exist on startup
    try:
        from app.db import Base, SessionLocal, engine
        import app.models  # ensure models are registered
        Base.metadata.create_all(bind=engine)

        from app.seed import ensure_seed_data
        with SessionLocal() as db:
            ensure_seed_data(db)
        logger.info("Database schema and initial seed verified.")
    except Exception as e:
        logger.error(f"Startup database initialization error: {e}", exc_info=True)
    yield


app = FastAPI(
    title="Retro Watches API",
    version="0.1.0",
    lifespan=lifespan,
    # No interactive docs in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Explicit origins and Vercel domains, credentials on for admin auth cookie
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
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
