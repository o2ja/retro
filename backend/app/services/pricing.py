"""Authoritative price and discount arithmetic.

Every number a customer ever sees or pays is produced here, on the server.
Two kinds of promotion exist:

* automatic  (``code IS NULL``) - applied to matching products in the catalog.
* coded      (``code`` set)     - only applied when the customer enters the code.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import DiscountType
from app.core.errors import AppError
from app.db import CENTS, utcnow
from app.models import Product, Promotion

ZERO = Decimal("0.00")


def to_money(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ProductPricing:
    """What the storefront is allowed to render for a product."""

    price: Decimal | None
    compare_at_price: Decimal | None
    estimated_market_price: Decimal | None
    discount_amount: Decimal
    final_price: Decimal | None
    discount_percent: int | None
    promotion_name: str | None
    price_on_request: bool


def is_promotion_live(promotion: Promotion, now: datetime | None = None) -> bool:
    now = now or utcnow()
    if not promotion.active:
        return False
    if promotion.starts_at and promotion.starts_at > now:
        return False
    if promotion.ends_at and promotion.ends_at < now:
        return False
    return not (
        promotion.usage_limit is not None
        and promotion.usage_count >= promotion.usage_limit
    )


def discount_for(promotion: Promotion, amount: Decimal) -> Decimal:
    """Discount on `amount`, never negative and never more than the amount."""
    if amount <= ZERO:
        return ZERO
    if promotion.discount_type is DiscountType.PERCENTAGE:
        raw = amount * (promotion.discount_value / Decimal("100"))
    else:
        raw = promotion.discount_value
    return min(to_money(max(raw, ZERO)), amount)


def promotion_applies_to(promotion: Promotion, product: Product) -> bool:
    """No targeting at all means the promotion covers the whole catalog."""
    if not promotion.products and not promotion.categories:
        return True
    if any(p.id == product.id for p in promotion.products):
        return True
    product_category_ids = {c.id for c in product.categories}
    return any(c.id in product_category_ids for c in promotion.categories)


def live_automatic_promotions(
    db: Session, now: datetime | None = None
) -> list[Promotion]:
    now = now or utcnow()
    stmt = (
        select(Promotion)
        .options(selectinload(Promotion.products), selectinload(Promotion.categories))
        .where(
            Promotion.code.is_(None),
            Promotion.active.is_(True),
            or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
            or_(Promotion.ends_at.is_(None), Promotion.ends_at >= now),
        )
    )
    return [p for p in db.execute(stmt).scalars().all() if is_promotion_live(p, now)]


def price_product(
    product: Product, promotions: list[Promotion] | None = None
) -> ProductPricing:
    """Resolve a product's displayed pricing against the automatic promotions given.

    A product without a selling price is "price on request": the catalog holds an
    estimated market value only, and inventing a selling price is not allowed.
    """
    price = product.price
    if price is None:
        return ProductPricing(
            price=None,
            compare_at_price=product.compare_at_price,
            estimated_market_price=product.estimated_market_price,
            discount_amount=ZERO,
            final_price=None,
            discount_percent=None,
            promotion_name=None,
            price_on_request=True,
        )

    best_discount = ZERO
    best_promotion: Promotion | None = None
    for promotion in promotions or []:
        if not promotion_applies_to(promotion, product):
            continue
        candidate = discount_for(promotion, price)
        if candidate > best_discount:
            best_discount, best_promotion = candidate, promotion

    final_price = to_money(price - best_discount)
    reference = product.compare_at_price or price
    percent = None
    if reference and reference > ZERO and final_price < reference:
        percent = int(
            ((reference - final_price) / reference * 100).quantize(Decimal("1"))
        )

    return ProductPricing(
        price=to_money(price),
        compare_at_price=product.compare_at_price,
        estimated_market_price=product.estimated_market_price,
        discount_amount=best_discount,
        final_price=final_price,
        discount_percent=percent,
        promotion_name=best_promotion.name if best_promotion else None,
        price_on_request=False,
    )


def validate_promotion_code(db: Session, code: str, subtotal: Decimal) -> Promotion:
    """Server-side eligibility check for a customer-entered code.

    Raises AppError with a customer-safe message; never reveals whether a code
    exists but is merely expired versus never existed.
    """
    normalized = code.strip().upper()
    promotion = db.execute(
        select(Promotion)
        .options(selectinload(Promotion.products), selectinload(Promotion.categories))
        .where(func.upper(Promotion.code) == normalized)
    ).scalar_one_or_none()

    if promotion is None or not is_promotion_live(promotion):
        raise AppError("This promotion code is not valid.", code="invalid_promotion")
    if (
        promotion.minimum_order_value is not None
        and subtotal < promotion.minimum_order_value
    ):
        raise AppError(
            f"This code requires a minimum order of {promotion.minimum_order_value}.",
            code="promotion_minimum_not_met",
        )
    return promotion


def _self_check() -> None:
    """Runnable check for the money paths: percentage, fixed, clamping, rounding."""
    from types import SimpleNamespace

    percent = SimpleNamespace(
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal("12.5"),
        products=[],
        categories=[],
        name="Winter",
    )
    fixed = SimpleNamespace(
        discount_type=DiscountType.FIXED_AMOUNT,
        discount_value=Decimal("500"),
        products=[],
        categories=[],
        name="Flat",
    )
    assert discount_for(percent, Decimal("20000.00")) == Decimal("2500.00")
    assert discount_for(percent, Decimal("100.01")) == Decimal("12.50")  # half-up
    assert discount_for(fixed, Decimal("300.00")) == Decimal("300.00")  # clamped
    assert discount_for(fixed, ZERO) == ZERO

    product = SimpleNamespace(
        id=1,
        price=Decimal("20000.00"),
        compare_at_price=Decimal("22000.00"),
        estimated_market_price=Decimal("20000.00"),
        categories=[],
    )
    priced = price_product(product, [percent])
    assert priced.final_price == Decimal("17500.00"), priced
    assert priced.discount_percent == 20, priced

    unpriced = SimpleNamespace(
        id=2,
        price=None,
        compare_at_price=None,
        estimated_market_price=Decimal("19000.00"),
        categories=[],
    )
    assert price_product(unpriced, [percent]).price_on_request is True
    print("pricing self-check ok")


if __name__ == "__main__":
    _self_check()
