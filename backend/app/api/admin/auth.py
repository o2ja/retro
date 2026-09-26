"""Admin authentication: signed HTTP-only session cookie, rate-limited login."""

from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select

from app.api.deps import CurrentAdmin, DbSession
from app.core import ratelimit
from app.core.config import settings
from app.core.errors import AuthError
from app.core.security import (
    create_session_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.db import utcnow
from app.models import AdminUser
from app.schemas import AdminLoginIn, AdminMeOut, MessageOut
from app.services import audit

router = APIRouter(prefix="/api/admin", tags=["admin:auth"])


def _set_session_cookie(response: Response, admin_id: int) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_token(admin_id),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=AdminMeOut)
def login(
    request: Request, response: Response, db: DbSession, payload: AdminLoginIn
) -> AdminUser:
    client_ip = request.client.host if request.client else "unknown"
    ratelimit.enforce(
        f"admin-login:{client_ip}",
        limit=settings.login_rate_limit_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )

    admin = db.execute(
        select(AdminUser).where(func.lower(AdminUser.email) == payload.email.lower())
    ).scalar_one_or_none()

    # One generic message for every failure: no account enumeration.
    if (
        admin is None
        or not admin.is_active
        or not verify_password(payload.password, admin.password_hash)
    ):
        raise AuthError("Invalid email or password.")

    if needs_rehash(admin.password_hash):
        admin.password_hash = hash_password(payload.password)

    admin.last_login_at = utcnow()
    audit.record(
        db,
        admin_user_id=admin.id,
        action="admin.login",
        entity_type="admin_user",
        entity_id=admin.id,
    )
    db.commit()

    ratelimit.reset(f"admin-login:{client_ip}")
    _set_session_cookie(response, admin.id)
    return admin


@router.post("/logout", response_model=MessageOut)
def logout(response: Response) -> MessageOut:
    response.delete_cookie(settings.session_cookie_name, path="/")
    return MessageOut(message="Signed out")


@router.get("/me", response_model=AdminMeOut)
def me(admin: CurrentAdmin) -> AdminUser:
    return admin
