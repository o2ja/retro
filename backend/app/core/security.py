"""Password hashing and signed admin session cookies.

No JWT library: the admin session is a signed, expiring cookie payload, which is
all this app needs. Argon2id is the hashing algorithm.
"""

from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

_hasher = PasswordHasher()
_serializer = URLSafeTimedSerializer(settings.secret_key, salt="obaidi-admin-session")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return True


def create_session_token(admin_user_id: int) -> str:
    return _serializer.dumps({"sub": admin_user_id})


def read_session_token(token: str) -> int | None:
    """Return the admin id, or None when the cookie is invalid or expired."""
    try:
        payload: Any = _serializer.loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    subject = payload.get("sub") if isinstance(payload, dict) else None
    return subject if isinstance(subject, int) else None
