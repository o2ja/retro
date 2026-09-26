"""Stripe provider.

Talks to Stripe's REST API with httpx and verifies webhooks with stdlib HMAC,
so there is no SDK to keep in step. It is registered only when
`PAYMENT_PROVIDER=stripe` and the keys are present; otherwise the app keeps
using `UnconfiguredProvider` and refuses every payment.

Stripe is the reference implementation of the `PaymentProvider` protocol. To use
a different processor, write one more class with these four methods and register
it — nothing outside this package needs to change.
"""

import hashlib
import hmac
import json
import time
from decimal import Decimal

import httpx

from app.core.config import settings
from app.core.enums import PaymentStatus
from app.core.errors import AppError
from app.payments.base import PaymentSession, PaymentVerification

API_ROOT = "https://api.stripe.com/v1"
TIMEOUT = httpx.Timeout(20.0)

# Stripe rejects a signature whose timestamp is too old; this bounds replay.
WEBHOOK_TOLERANCE_SECONDS = 300

# Stripe works in the smallest currency unit. Currencies without minor units
# would need a different factor; the store is USD.
MINOR_UNITS = 100

_STATUS_MAP = {
    "paid": PaymentStatus.PAID,
    "complete": PaymentStatus.PAID,
    "succeeded": PaymentStatus.PAID,
    "unpaid": PaymentStatus.PENDING,
    "no_payment_required": PaymentStatus.PAID,
    "requires_payment_method": PaymentStatus.FAILED,
    "canceled": PaymentStatus.CANCELLED,
    "expired": PaymentStatus.CANCELLED,
}


def to_minor(amount: Decimal) -> int:
    return int((amount * MINOR_UNITS).to_integral_value())


def from_minor(amount: int, currency: str) -> Decimal:
    return (Decimal(amount) / MINOR_UNITS).quantize(Decimal("0.01"))


class StripeProvider:
    name = "stripe"

    def __init__(self) -> None:
        if not settings.payment_secret_key:
            raise AppError(
                "Payment is not configured.",
                code="payment_provider_unconfigured",
                status_code=503,
            )
        self._auth = (settings.payment_secret_key, "")

    # ----------------------------------------------------------------- HTTP --
    def _post(self, path: str, data: dict) -> dict:
        try:
            response = httpx.post(
                f"{API_ROOT}{path}", data=data, auth=self._auth, timeout=TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise AppError(
                "Could not reach the payment provider.",
                code="payment_provider_unreachable",
                status_code=502,
            ) from exc
        return self._unwrap(response)

    def _get(self, path: str) -> dict:
        try:
            response = httpx.get(f"{API_ROOT}{path}", auth=self._auth, timeout=TIMEOUT)
        except httpx.HTTPError as exc:
            raise AppError(
                "Could not reach the payment provider.",
                code="payment_provider_unreachable",
                status_code=502,
            ) from exc
        return self._unwrap(response)

    @staticmethod
    def _unwrap(response: httpx.Response) -> dict:
        payload = response.json() if response.content else {}
        if response.is_success:
            return payload
        # The provider's own message may name internals; keep it out of the API.
        raise AppError(
            "The payment provider rejected this request.",
            code="payment_provider_error",
            status_code=502,
        )

    # ------------------------------------------------------------ protocol --
    def create_session(
        self,
        *,
        order_number: str,
        amount: Decimal,
        currency: str,
        customer_email: str,
        return_url: str,
    ) -> PaymentSession:
        data = {
            "mode": "payment",
            "customer_email": customer_email,
            "client_reference_id": order_number,
            "success_url": f"{return_url.rstrip('/')}/order/{order_number}",
            "cancel_url": f"{return_url.rstrip('/')}/cart",
            "line_items[0][quantity]": 1,
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][unit_amount]": to_minor(amount),
            "line_items[0][price_data][product_data][name]": (
                f"Retro Watches order {order_number}"
            ),
            "metadata[order_number]": order_number,
            # Stripe replays this key instead of charging twice on a retry.
            "payment_intent_data[metadata][order_number]": order_number,
        }
        session = self._post("/checkout/sessions", data)
        return PaymentSession(
            provider=self.name,
            provider_payment_id=str(session["id"]),
            redirect_url=session.get("url"),
        )

    def verify_payment(self, provider_payment_id: str) -> PaymentVerification:
        """Ask Stripe directly. Used to confirm a return without a webhook."""
        session = self._get(f"/checkout/sessions/{provider_payment_id}")
        return self._to_verification(session)

    def parse_webhook(
        self, payload: bytes, headers: dict[str, str]
    ) -> PaymentVerification:
        event = self._verified_event(payload, headers)
        obj = event.get("data", {}).get("object", {})
        verification = self._to_verification(obj)
        # The event id is what makes replay handling idempotent.
        return PaymentVerification(
            provider_payment_id=verification.provider_payment_id,
            status=verification.status,
            amount=verification.amount,
            currency=verification.currency,
            provider_event_id=str(event.get("id")) if event.get("id") else None,
            failure_reason=verification.failure_reason,
        )

    def refund(self, provider_payment_id: str, amount: Decimal) -> PaymentVerification:
        session = self._get(f"/checkout/sessions/{provider_payment_id}")
        intent = session.get("payment_intent")
        if not intent:
            raise AppError("This payment cannot be refunded.", code="refund_unavailable")
        self._post("/refunds", {"payment_intent": intent, "amount": to_minor(amount)})
        return PaymentVerification(
            provider_payment_id=provider_payment_id,
            status=PaymentStatus.REFUNDED,
            amount=amount,
            currency=str(session.get("currency", "usd")).upper(),
        )

    # ------------------------------------------------------------ internals --
    def _to_verification(self, obj: dict) -> PaymentVerification:
        raw_status = str(obj.get("payment_status") or obj.get("status") or "")
        currency = str(obj.get("currency") or "usd").upper()
        amount = from_minor(
            int(obj.get("amount_total") or obj.get("amount") or 0), currency
        )
        status = _STATUS_MAP.get(raw_status, PaymentStatus.PENDING)
        return PaymentVerification(
            provider_payment_id=str(obj.get("id", "")),
            status=status,
            amount=amount,
            currency=currency,
            failure_reason=None if status is not PaymentStatus.FAILED else raw_status,
        )

    def _verified_event(self, payload: bytes, headers: dict[str, str]) -> dict:
        """Reject anything that is not a correctly signed, recent Stripe event."""
        secret = settings.payment_webhook_secret
        if not secret:
            raise AppError(
                "Webhook secret is not configured.",
                code="webhook_not_configured",
                status_code=503,
            )

        signature_header = headers.get("stripe-signature") or headers.get(
            "Stripe-Signature", ""
        )
        parts = dict(
            piece.split("=", 1) for piece in signature_header.split(",") if "=" in piece
        )
        timestamp = parts.get("t")
        signature = parts.get("v1")
        if not timestamp or not signature:
            raise AppError(
                "Invalid webhook signature.", code="invalid_webhook", status_code=400
            )

        if abs(time.time() - int(timestamp)) > WEBHOOK_TOLERANCE_SECONDS:
            raise AppError(
                "Webhook timestamp out of range.", code="invalid_webhook", status_code=400
            )

        expected = hmac.new(
            secret.encode(),
            f"{timestamp}.".encode() + payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise AppError(
                "Invalid webhook signature.", code="invalid_webhook", status_code=400
            )

        return json.loads(payload.decode())


def sign_webhook(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Build a Stripe-format signature header. Used by the webhook tests."""
    ts = timestamp if timestamp is not None else int(time.time())
    digest = hmac.new(
        secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={digest}"
