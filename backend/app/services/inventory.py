"""Stock is business data: it only ever changes here, inside a transaction."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Availability, InventoryReason
from app.core.errors import AppError, NotFoundError
from app.models import Inventory, InventoryTransaction, Product


def ensure_record(db: Session, product_id: int) -> Inventory:
    record = db.execute(
        select(Inventory).where(Inventory.product_id == product_id)
    ).scalar_one_or_none()
    if record is None:
        record = Inventory(product_id=product_id, quantity=0, low_stock_threshold=1)
        db.add(record)
        db.flush()
    return record


def adjust(
    db: Session,
    product_id: int,
    change: int,
    reason: InventoryReason,
    *,
    reference_type: str | None = None,
    reference_id: str | None = None,
    note: str | None = None,
) -> Inventory:
    """Apply a signed stock change and record the transaction.

    The row is locked for update so two concurrent checkouts cannot both read the
    last unit. Going below zero is refused rather than clamped - overselling must
    fail loudly.
    """
    record = db.execute(
        select(Inventory).where(Inventory.product_id == product_id).with_for_update()
    ).scalar_one_or_none()
    if record is None:
        record = ensure_record(db, product_id)

    new_quantity = record.quantity + change
    if new_quantity < 0:
        raise AppError(
            "Not enough stock available.",
            code="insufficient_stock",
            status_code=409,
        )

    record.quantity = new_quantity
    db.add(
        InventoryTransaction(
            product_id=product_id,
            change_quantity=change,
            quantity_after=new_quantity,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
        )
    )
    db.flush()
    return record


def set_quantity(
    db: Session,
    product_id: int,
    quantity: int,
    reason: InventoryReason = InventoryReason.MANUAL_ADJUSTMENT,
    *,
    note: str | None = None,
) -> Inventory:
    """Admin-facing absolute set, recorded as the delta it really is."""
    if quantity < 0:
        raise AppError("Quantity cannot be negative.", code="invalid_quantity")
    record = ensure_record(db, product_id)
    return adjust(db, product_id, quantity - record.quantity, reason, note=note)


def availability(product: Product) -> Availability:
    """Derived, never stored: publication state plus stock decide what customers see."""
    if not product.active:
        return Availability.HIDDEN
    record = product.inventory
    quantity = record.quantity if record else 0
    threshold = record.low_stock_threshold if record else 1
    if quantity <= 0:
        return Availability.SOLD if product.is_unique else Availability.OUT_OF_STOCK
    # A one-of-a-kind piece is never "low stock" - one is the whole stock.
    if product.is_unique:
        return Availability.IN_STOCK
    if quantity <= threshold:
        return Availability.LOW_STOCK
    return Availability.IN_STOCK


def require_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found")
    return product
