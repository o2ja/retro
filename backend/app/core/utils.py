"""Small shared helpers."""

import re
import secrets
import unicodedata
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    return _NON_SLUG.sub("-", ascii_value.lower()).strip("-") or "item"


def unique_slug(
    db: Session, model: type, value: str, *, exclude_id: int | None = None
) -> str:
    """Append -2, -3 ... until the slug is free."""
    base = slugify(value)
    candidate = base
    suffix = 1
    while True:
        stmt = select(model.id).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if db.execute(stmt).first() is None:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


def paginate(db: Session, stmt: Select, page: int, page_size: int) -> tuple[list, int]:
    """Return (items, total) for a select, using one count query and one page query."""
    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    items = (
        db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
        .unique()
        .scalars()
        .all()
    )
    return list(items), int(total)


def generate_order_number(now: datetime) -> str:
    """OT-YYYYMMDD-XXXXXX, unpredictable enough not to be enumerable."""
    return f"OT-{now:%Y%m%d}-{secrets.token_hex(3).upper()}"
