"""Payment provider abstraction: the protocol and the refuse-everything default.

NOT IMPLEMENTED YET - by design. Phase 4 registers a real provider here. Until
then `get_provider()` returns a provider that refuses every call, so there is no
path anywhere in this codebase that can mark an order paid without a real,
server-verified provider response.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.core.enums import PaymentStatus
from app.core.errors import AppError


@dataclass(frozen=True)
class PaymentSession:
    """What the frontend needs to hand the customer to the provider."""

    provider: str
    provider_payment_id: str
    redirect_url: str | None = None
    client_secret: str | None = None


@dataclass(frozen=True)
class PaymentVerification:
    """The provider's own answer about a payment. The only source of truth."""

    provider_payment_id: str
    status: PaymentStatus
    amount: Decimal
    currency: str
    provider_event_id: str | None = None
    failure_reason: str | None = None


@runtime_checkable
class PaymentProvider(Protocol):
    name: str

    def create_session(
        self,
        *,
        order_number: str,
        amount: Decimal,
        currency: str,
        customer_email: str,
        return_url: str,
    ) -> PaymentSession: ...

    def verify_payment(self, provider_payment_id: str) -> PaymentVerification: ...

    def parse_webhook(
        self, payload: bytes, headers: dict[str, str]
    ) -> PaymentVerification: ...

    def refund(
        self, provider_payment_id: str, amount: Decimal
    ) -> PaymentVerification: ...


class UnconfiguredProvider:
    """Placeholder. Every method fails loudly; nothing here can fake a payment."""

    name = "unconfigured"

    def _fail(self) -> None:
        raise AppError(
            "Online payment is not available yet.",
            code="payment_provider_unconfigured",
            status_code=503,
        )

    def create_session(self, **_: object) -> PaymentSession:
        self._fail()
        raise AssertionError("unreachable")

    def verify_payment(self, provider_payment_id: str) -> PaymentVerification:
        self._fail()
        raise AssertionError("unreachable")

    def parse_webhook(
        self, payload: bytes, headers: dict[str, str]
    ) -> PaymentVerification:
        self._fail()
        raise AssertionError("unreachable")

    def refund(self, provider_payment_id: str, amount: Decimal) -> PaymentVerification:
        self._fail()
        raise AssertionError("unreachable")
