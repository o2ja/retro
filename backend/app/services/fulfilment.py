"""Turning a paid cart into an order.

Two moments, deliberately separate:

1. `open_order` — called when a payment session is created. Writes the order in
   PENDING_PAYMENT and **holds the stock**, so two people cannot both buy the
   one Rolex while their cards are processing.
2. `confirm_payment` — called from the verified webhook (or a server-side
   verification). Flips the order to PAYMENT_CONFIRMED. The stock is already
   held, so a replayed webhook cannot decrement anything twice.

Held stock is returned by `orders.transition` whenever an order leaves for
CANCELLED or REFUNDED, so restoration lives in exactly one place.

Nothing here trusts the browser: amounts are re-checked against the provider's
own numbers before an order is marked paid.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import InventoryReason, OrderStatus, PaymentStatus
from app.core.errors import AppError, ConflictError
from app.core.utils import generate_order_number
from app.db import utcnow
from app.models import Customer, Inquiry, Order, OrderItem, Payment, Product
from app.payments.base import PaymentVerification
from app.schemas import ShippingDetailsIn
from app.services import audit, checkout, inventory


def upsert_customer(
    db: Session, *, email: str, full_name: str, phone: str | None
) -> Customer:
    """Every buyer gets a customer record, keyed on email."""
    email = email.lower()
    customer = db.execute(
        select(Customer).where(Customer.email == email)
    ).scalar_one_or_none()
    if customer is None:
        customer = Customer(email=email)
        db.add(customer)
    customer.full_name = full_name
    customer.phone = phone or customer.phone
    db.flush()
    return customer


def open_order(
    db: Session,
    quote: checkout.Quote,
    shipping: ShippingDetailsIn,
) -> Order:
    """Create a PENDING_PAYMENT order and hold its stock, inside one transaction."""
    if not quote.lines:
        raise AppError("Your bag is empty.", code="empty_cart")
    if quote.issues:
        raise ConflictError(quote.issues[0]["message"])

    customer = upsert_customer(
        db, email=shipping.email, full_name=shipping.full_name, phone=shipping.phone
    )
    order = Order(
        order_number=generate_order_number(utcnow()),
        customer_id=customer.id,
        subtotal=quote.subtotal,
        discount_total=quote.discount_total,
        shipping_total=quote.shipping_total,
        total=quote.total,
        currency=quote.currency,
        payment_status=PaymentStatus.PENDING,
        order_status=OrderStatus.PENDING_PAYMENT,
        promotion_id=quote.promotion.id if quote.promotion else None,
        promotion_code_snapshot=quote.promotion.code if quote.promotion else None,
        shipping_name=shipping.full_name,
        shipping_email=shipping.email,
        shipping_phone=shipping.phone,
        shipping_address=shipping.address,
        shipping_city=shipping.city,
        shipping_country=shipping.country,
        shipping_postal_code=shipping.postal_code,
        customer_note=shipping.note,
    )

    for line in quote.lines:
        product = db.get(Product, line.product_id)
        order.items.append(
            OrderItem(
                product_id=line.product_id,
                product_name_snapshot=line.name,
                brand_name_snapshot=line.brand_name,
                sku_snapshot=line.sku,
                reference_number_snapshot=product.reference_number if product else None,
                image_url_snapshot=line.image_url,
                unit_price=line.unit_price,
                quantity=line.quantity,
                discount_amount=line.discount_amount,
                line_total=line.line_total,
            )
        )
    db.add(order)
    db.flush()

    # Hold the stock now. `adjust` locks the row and refuses to go negative, so
    # a simultaneous checkout for the last piece fails here rather than
    # overselling.
    for line in quote.lines:
        inventory.adjust(
            db,
            line.product_id,
            -line.quantity,
            InventoryReason.ORDER_CONFIRMED,
            reference_type="order",
            reference_id=order.order_number,
            note="Held for pending payment",
        )
    return order


def open_sale(
    db: Session,
    inquiry: Inquiry,
    product: Product,
    price: Decimal,
    note: str | None,
) -> Order:
    """Record a sale agreed in conversation: the order, its line, and the held stock.

    Starts in PENDING_PAYMENT like any order; `record_offline_payment` marks it paid.
    """
    customer = upsert_customer(
        db, email=inquiry.email, full_name=inquiry.full_name, phone=inquiry.phone
    )
    primary = next((i for i in product.images if i.is_primary), None)
    order = Order(
        order_number=generate_order_number(utcnow()),
        customer_id=customer.id,
        subtotal=price,
        discount_total=Decimal("0.00"),
        shipping_total=Decimal("0.00"),
        total=price,
        currency=product.currency,
        payment_status=PaymentStatus.PENDING,
        order_status=OrderStatus.PENDING_PAYMENT,
        shipping_name=inquiry.full_name,
        shipping_email=inquiry.email,
        shipping_phone=inquiry.phone,
        # Handed over in person unless the store adds delivery details later.
        shipping_address="",
        shipping_city="",
        shipping_country="",
        customer_note=note,
    )
    order.items.append(
        OrderItem(
            product_id=product.id,
            product_name_snapshot=product.name,
            brand_name_snapshot=product.brand.name if product.brand else None,
            sku_snapshot=product.sku,
            reference_number_snapshot=product.reference_number,
            image_url_snapshot=primary.url if primary else None,
            unit_price=price,
            quantity=1,
            line_total=price,
        )
    )
    db.add(order)
    db.flush()

    # Same guard as checkout: the last piece cannot be sold twice.
    inventory.adjust(
        db,
        product.id,
        -1,
        InventoryReason.ORDER_CONFIRMED,
        reference_type="order",
        reference_id=order.order_number,
        note=f"Sold from request #{inquiry.id}",
    )
    return order


def record_offline_payment(
    db: Session, order: Order, method: str, reference: str | None
) -> Order:
    """Mark an order paid for money taken in person or by transfer.

    This is the one path that marks an order paid without a payment provider, so
    it only runs from an authenticated admin action and is always audited.
    """
    if order.payment_status is PaymentStatus.PAID:
        raise ConflictError("This order is already paid.")
    if order.order_status is not OrderStatus.PENDING_PAYMENT:
        raise ConflictError("Only an order awaiting payment can be marked paid.")
    return confirm_payment(
        db,
        order,
        method,
        PaymentVerification(
            provider_payment_id=reference or f"{method}-{order.order_number}",
            status=PaymentStatus.PAID,
            amount=Decimal(order.total),
            currency=order.currency,
        ),
    )


def record_payment(
    db: Session,
    order: Order,
    provider: str,
    verification: PaymentVerification,
) -> Payment:
    payment = db.execute(
        select(Payment).where(
            Payment.order_id == order.id,
            Payment.provider == provider,
            Payment.provider_payment_id == verification.provider_payment_id,
        )
    ).scalar_one_or_none()
    if payment is None:
        payment = Payment(
            order_id=order.id,
            provider=provider,
            provider_payment_id=verification.provider_payment_id,
            amount=verification.amount,
            currency=verification.currency,
        )
        db.add(payment)
    payment.status = verification.status
    payment.failure_reason = verification.failure_reason
    if verification.provider_event_id:
        payment.provider_event_id = verification.provider_event_id
    db.flush()
    return payment


def already_processed(db: Session, event_id: str | None) -> bool:
    """Webhooks are retried; an event we have already stored is a no-op."""
    if not event_id:
        return False
    return (
        db.execute(
            select(Payment.id).where(Payment.provider_event_id == event_id)
        ).first()
        is not None
    )


def find_order(db: Session, order_number: str) -> Order | None:
    return (
        db.execute(
            select(Order)
            .options(selectinload(Order.items), selectinload(Order.payments))
            .where(Order.order_number == order_number)
        )
        .unique()
        .scalar_one_or_none()
    )


def confirm_payment(
    db: Session,
    order: Order,
    provider: str,
    verification: PaymentVerification,
) -> Order:
    """Apply a provider-verified result to an order.

    The amount and currency the provider reports must match the order we wrote.
    A mismatch is never accepted — it means the total was altered somewhere
    between the quote and the charge.
    """
    from app.services import orders as order_service

    if verification.status is PaymentStatus.PAID:
        if verification.currency.upper() != order.currency.upper():
            raise ConflictError("Payment currency does not match the order.")
        if Decimal(verification.amount) != Decimal(order.total):
            raise ConflictError("Payment amount does not match the order total.")

    record_payment(db, order, provider, verification)

    if verification.status is PaymentStatus.PAID:
        if order.payment_status is PaymentStatus.PAID:
            return order  # Replay: already confirmed, stock already held.
        order.payment_status = PaymentStatus.PAID
        if order.order_status is OrderStatus.PENDING_PAYMENT:
            order_service.transition(
                db, order, OrderStatus.PAYMENT_CONFIRMED, note="Payment verified"
            )
        if order.customer_id:
            customer = db.get(Customer, order.customer_id)
            if customer:
                customer.last_order_at = utcnow()
        if order.promotion_id:
            from app.models import Promotion

            promotion = db.get(Promotion, order.promotion_id)
            if promotion:
                promotion.usage_count += 1

    elif verification.status in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
        order.payment_status = verification.status
        if order.order_status is OrderStatus.PENDING_PAYMENT:
            # transition() returns the held stock; see orders._STOCK_COMMITTED_STATUSES.
            order_service.transition(
                db, order, OrderStatus.CANCELLED, note="Payment not completed"
            )

    elif verification.status is PaymentStatus.REFUNDED:
        order.payment_status = PaymentStatus.REFUNDED
        if order_service.can_transition(order.order_status, OrderStatus.REFUNDED):
            order_service.transition(db, order, OrderStatus.REFUNDED, note="Refunded")

    audit.record(
        db,
        admin_user_id=None,
        action="payment.verified",
        entity_type="order",
        entity_id=order.id,
        summary=f"{provider}:{verification.status.value}",
    )
    db.flush()
    return order
