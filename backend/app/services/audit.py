"""Audit trail for meaningful admin actions. Never records secrets."""

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    *,
    admin_user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    summary: str | None = None,
) -> None:
    db.add(
        AuditLog(
            admin_user_id=admin_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            summary=summary[:500] if summary else None,
        )
    )
