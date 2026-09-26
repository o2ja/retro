"""Checkout API.

`/quote` is the number the customer sees. `/payment-session` is the only way to
start a payment, and it re-runs the whole quote first — a client that posts a
stale or tampered total gets the server's answer, not its own.

No endpoint here creates an order. An order comes into existence only after a
payment provider confirms payment server-side, which is Phase 4.
"""

from fastapi import APIRouter, Request

from app.api.deps import DbSession
from app.core import ratelimit
from app.core.config import settings
from app.core.enums import PaymentStatus
from app.core.errors import AppError
from app.payments import get_provider
from app.payments.base import PaymentVerification
from app.schemas import (
    CheckoutQuoteIn,
    CheckoutQuoteOut,
    PaymentSessionIn,
    PaymentSessionOut,
)
from app.services import checkout, fulfilment

router = APIRouter(prefix="/api/checkout", tags=["checkout"])


@router.post("/quote", response_model=CheckoutQuoteOut)
def quote_cart(db: DbSession, payload: CheckoutQuoteIn) -> CheckoutQuoteOut:
    """Price a cart server-side: stock, promotions and totals all revalidated."""
    result = checkout.quote(
        db,
        [(item.product_id, item.quantity) for item in payload.items],
        payload.promotion_code,
    )
    return CheckoutQuoteOut.build(result)


@router.post("/payment-session", response_model=PaymentSessionOut)
def create_payment_session(
    request: Request, db: DbSession, payload: PaymentSessionIn
) -> PaymentSessionOut:
    """Start a payment for a re-verified cart.

    Until a provider is registered (Phase 4) this returns 503 from
    `UnconfiguredProvider` — deliberately, so no checkout can ever appear to
    succeed without a real payment.
    """
    client_ip = request.client.host if request.client else "unknown"
    ratelimit.enforce(f"payment-session:{client_ip}", limit=10, window_seconds=60)

    result = checkout.quote(
        db,
        [(item.product_id, item.quantity) for item in payload.items],
        payload.promotion_code,
    )
    # Issues first: when every line fails, the customer needs the real reason,
    # not "your bag is empty".
    if result.issues:
        raise AppError(
            result.issues[0]["message"],
            code="cart_not_payable",
            status_code=409,
        )
    if not result.lines:
        raise AppError("Your bag is empty.", code="empty_cart")

    # The order is written first, in PENDING_PAYMENT, which is what holds the
    # stock while the card is processed. It is not a sale until the provider
    # says so; confirm_payment is the only thing that marks it paid.
    order = fulfilment.open_order(db, result, payload.shipping)
    try:
        session = get_provider().create_session(
            order_number=order.order_number,
            amount=order.total,
            currency=order.currency,
            customer_email=payload.shipping.email,
            return_url=settings.storefront_url,
        )
    except Exception:
        # No session, no order: give the held stock straight back.
        db.rollback()
        raise

    fulfilment.record_payment(
        db,
        order,
        session.provider,
        PaymentVerification(
            provider_payment_id=session.provider_payment_id,
            status=PaymentStatus.PENDING,
            amount=order.total,
            currency=order.currency,
        ),
    )
    db.commit()

    return PaymentSessionOut(
        provider=session.provider,
        provider_payment_id=session.provider_payment_id,
        redirect_url=session.redirect_url,
        client_secret=session.client_secret,
        order_number=order.order_number,
        total=order.total,
        currency=order.currency,
    )
