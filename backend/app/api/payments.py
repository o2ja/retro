"""Payment verification endpoints.

The webhook is the source of truth. A customer returning to the success page
proves nothing, so `/orders/{order_number}` re-asks the provider rather than
believing the redirect.
"""

from fastapi import APIRouter, Request

from app.api.deps import DbSession
from app.core.config import settings
from app.core.enums import PaymentStatus
from app.core.errors import AppError, NotFoundError
from app.payments import get_provider
from app.schemas import MessageOut, OrderDetailOut, PublicOrderOut
from app.services import fulfilment

router = APIRouter(prefix="/api", tags=["payments"])


@router.post("/payments/webhook/{provider}", response_model=MessageOut)
async def payment_webhook(provider: str, request: Request, db: DbSession) -> MessageOut:
    """Verified, idempotent, and safe to retry.

    An unsigned or stale payload is rejected before anything is read from it,
    and an event id we have already stored is acknowledged without being applied
    a second time.
    """
    if provider != settings.payment_provider:
        raise NotFoundError("Unknown payment provider")

    payload = await request.body()
    verification = get_provider(provider).parse_webhook(payload, dict(request.headers))

    if fulfilment.already_processed(db, verification.provider_event_id):
        # Stripe retries until it gets a 2xx; say yes without acting twice.
        return MessageOut(message="Already processed")

    order = _order_for(db, verification.provider_payment_id)
    if order is None:
        # Acknowledge unknown references so the provider stops retrying, but do
        # not invent an order for them.
        return MessageOut(message="No matching order")

    fulfilment.confirm_payment(db, order, provider, verification)
    db.commit()
    return MessageOut(message="Processed")


def _order_for(db, provider_payment_id: str):  # noqa: ANN001, ANN202
    from sqlalchemy import select

    from app.models import Order, Payment

    order_id = db.execute(
        select(Payment.order_id).where(Payment.provider_payment_id == provider_payment_id)
    ).scalar_one_or_none()
    if order_id is None:
        return None
    return db.get(Order, order_id)


@router.get("/orders/{order_number}", response_model=PublicOrderOut)
def get_order(db: DbSession, order_number: str, email: str) -> OrderDetailOut:
    """Order confirmation.

    The order number alone is not enough: the matching email must be supplied,
    so a guessed number reveals nothing. If the payment is still pending we ask
    the provider directly rather than reporting an unverified success.
    """
    order = fulfilment.find_order(db, order_number)
    if order is None or order.shipping_email.lower() != email.strip().lower():
        raise NotFoundError("Order not found")

    if order.payment_status is PaymentStatus.PENDING and order.payments:
        provider = settings.payment_provider
        reference = order.payments[-1].provider_payment_id
        if provider != "unconfigured" and reference:
            try:
                verification = get_provider(provider).verify_payment(reference)
                fulfilment.confirm_payment(db, order, provider, verification)
                db.commit()
                db.refresh(order)
            except AppError:
                # Provider unreachable: report what we actually know.
                db.rollback()

    return PublicOrderOut.build(order)
