"""Shared API dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AuthError
from app.core.security import read_session_token
from app.db import get_db
from app.models import AdminUser

DbSession = Annotated[Session, Depends(get_db)]


def current_admin(
    db: DbSession,
    session_cookie: Annotated[
        str | None, Cookie(alias=settings.session_cookie_name)
    ] = None,
) -> AdminUser:
    """Authorize an admin from the signed session cookie, or 401.

    Every admin route depends on this; there is no other way in.
    """
    if not session_cookie:
        raise AuthError
    admin_id = read_session_token(session_cookie)
    if admin_id is None:
        raise AuthError("Session expired. Please sign in again.")
    admin = db.get(AdminUser, admin_id)
    if admin is None or not admin.is_active:
        raise AuthError
    return admin


CurrentAdmin = Annotated[AdminUser, Depends(current_admin)]
