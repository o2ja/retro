"""Order status workflow.

Order creation belongs to the verified-payment flow (Phase 4). What lives here is
the part the admin dashboard needs now: validated status transitions, history and
the inventory consequences of cancelling or refunding.
"""

from sqlalchemy.orm import Session

from app.core.enums import (
    ORDER_STATUS_TRANSITIONS,
    InventoryReason,
    OrderStatus,
)
from app.core.errors import AppError
from app.models import Order, OrderStatusHistory
from app.services import audit, inventory

_RESTOCKING_STATUSES = {OrderStatus.CANCELLED, OrderStatus.REFUNDED}
_STOCK_COMMITTED_STATUSES = {
    # Stock is held from the moment the order is opened, so cancelling a
    # never-paid order must give it back too.
    OrderStatus.PENDING_PAYMENT,
    OrderStatus.PAYMENT_CONFIRMED,
    OrderStatus.PROCESSING,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
}


def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ORDER_STATUS_TRANSITIONS.get(current, frozenset())


def transition(
    db: Session,
    order: Order,
    target: OrderStatus,
    *,
    admin_user_id: int | None = None,
    note: str | None = None,
) -> Order:
    """Move an order to `target`, or refuse. Caller owns the commit."""
    current = order.order_status
    if current is target:
        raise AppError(
            f"Order is already {target.value}.", code="invalid_status_transition"
        )
    if not can_transition(current, target):
        raise AppError(
            f"Cannot move an order from {current.value} to {target.value}.",
            code="invalid_status_transition",
        )

    restock = target in _RESTOCKING_STATUSES and current in _STOCK_COMMITTED_STATUSES
    order.order_status = target
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=current,
            to_status=target,
            note=note,
            changed_by_admin_id=admin_user_id,
        )
    )

    if restock:
        reason = (
            InventoryReason.ORDER_CANCELLED
            if target is OrderStatus.CANCELLED
            else InventoryReason.RETURN
        )
        for item in order.items:
            if item.product_id is None:
                continue
            inventory.adjust(
                db,
                item.product_id,
                item.quantity,
                reason,
                reference_type="order",
                reference_id=order.order_number,
            )

    audit.record(
        db,
        admin_user_id=admin_user_id,
        action="order.status_changed",
        entity_type="order",
        entity_id=order.id,
        summary=f"{current.value} -> {target.value}",
    )
    db.flush()
    return order
