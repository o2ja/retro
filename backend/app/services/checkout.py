"""Authoritative checkout arithmetic.

The browser sends product ids and quantities. Nothing else it sends about money
is trusted: prices, discounts, availability and the total are all recomputed
here from the database.

Order creation is NOT here. An order exists only once a payment provider has
confirmed payment server-side (Phase 4).
"""

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.enums import Availability
from app.core.errors import AppError
from app.models import Product, Promotion
from app.services import catalog, inventory, pricing

ZERO = Decimal("0.00")

# ponytail: shipping is quoted at zero until the owner defines real rates or
# zones. Replace with a rate table here when shipping is actually charged.
SHIPPING_TOTAL = ZERO


@dataclass(frozen=True)
class QuoteLine:
    product_id: int
    slug: str
    name: str
    brand_name: str | None
    sku: str
    image_url: str | None
    unit_price: Decimal
    quantity: int
    discount_amount: Decimal
    line_total: Decimal
    availability: Availability


@dataclass
class Quote:
    lines: list[QuoteLine] = field(default_factory=list)
    subtotal: Decimal = ZERO
    discount_total: Decimal = ZERO
    shipping_total: Decimal = SHIPPING_TOTAL
    total: Decimal = ZERO
    currency: str = "USD"
    promotion: Promotion | None = None
    # Lines the customer must fix before paying; never silently dropped.
    issues: list[dict] = field(default_factory=list)

    @property
    def is_payable(self) -> bool:
        return bool(self.lines) and not self.issues


def _issue(product: Product | None, product_id: int, code: str, message: str) -> dict:
    return {
        "product_id": product_id,
        "product_name": product.name if product else None,
        "code": code,
        "message": message,
    }


def quote(
    db: Session,
    requested: list[tuple[int, int]],
    promotion_code: str | None = None,
) -> Quote:
    """Price a cart. `requested` is [(product_id, quantity)] straight from the client."""
    result = Quote()
    if not requested:
        return result

    products = {
        p.id: p
        for p in db.execute(
            catalog.product_query(published_only=True).where(
                Product.id.in_([pid for pid, _ in requested])
            )
        )
        .unique()
        .scalars()
        .all()
    }
    automatic = pricing.live_automatic_promotions(db)

    for product_id, quantity in requested:
        product = products.get(product_id)

        if product is None:
            result.issues.append(
                _issue(
                    None, product_id, "unavailable", "This item is no longer available."
                )
            )
            continue
        if quantity < 1:
            result.issues.append(
                _issue(
                    product,
                    product_id,
                    "invalid_quantity",
                    "Quantity must be at least 1.",
                )
            )
            continue

        priced = pricing.price_product(product, automatic)
        if priced.final_price is None:
            result.issues.append(
                _issue(
                    product,
                    product_id,
                    "price_on_request",
                    f"{product.name} is priced on request. Please contact us to buy it.",
                )
            )
            continue

        availability = inventory.availability(product)
        in_stock = product.inventory.quantity if product.inventory else 0
        if in_stock < quantity:
            result.issues.append(
                _issue(
                    product,
                    product_id,
                    "insufficient_stock",
                    f"Only {in_stock} available of {product.name}."
                    if in_stock
                    else f"{product.name} is no longer available.",
                )
            )
            continue

        line_total = pricing.to_money(priced.final_price * quantity)
        primary = next(
            (i for i in product.images if i.is_primary),
            product.images[0] if product.images else None,
        )
        result.lines.append(
            QuoteLine(
                product_id=product.id,
                slug=product.slug,
                name=product.name,
                brand_name=product.brand.name if product.brand else None,
                sku=product.sku,
                image_url=primary.url if primary else None,
                unit_price=priced.final_price,
                quantity=quantity,
                discount_amount=pricing.to_money(priced.discount_amount * quantity),
                line_total=line_total,
                availability=availability,
            )
        )
        result.currency = product.currency

    result.subtotal = pricing.to_money(
        sum((line.line_total for line in result.lines), ZERO)
    )

    if promotion_code and result.lines:
        promotion = pricing.validate_promotion_code(db, promotion_code, result.subtotal)
        eligible = pricing.to_money(
            sum(
                (
                    line.line_total
                    for line in result.lines
                    if pricing.promotion_applies_to(promotion, products[line.product_id])
                ),
                ZERO,
            )
        )
        if eligible <= ZERO:
            raise AppError(
                "This code does not apply to anything in your bag.",
                code="promotion_not_applicable",
            )
        result.promotion = promotion
        result.discount_total = pricing.discount_for(promotion, eligible)

    result.total = pricing.to_money(
        max(result.subtotal - result.discount_total, ZERO) + result.shipping_total
    )
    return result
