"""Payment provider registry.

`get_provider()` returns whatever `PAYMENT_PROVIDER` names. Until that is set to
a configured provider it returns `UnconfiguredProvider`, which raises 503 on
every method — so no code path anywhere can mark an order paid without a real,
server-verified provider response.
"""

from app.core.config import settings
from app.core.errors import AppError
from app.payments.base import (
    PaymentProvider,
    PaymentSession,
    PaymentVerification,
    UnconfiguredProvider,
)

__all__ = [
    "PaymentProvider",
    "PaymentSession",
    "PaymentVerification",
    "UnconfiguredProvider",
    "get_provider",
]


def _registry() -> dict[str, type]:
    """Imported lazily so a missing provider dependency cannot break startup."""
    providers: dict[str, type] = {"unconfigured": UnconfiguredProvider}
    from app.payments.stripe import StripeProvider

    providers["stripe"] = StripeProvider
    return providers


def get_provider(name: str | None = None) -> PaymentProvider:
    provider_cls = _registry().get(name or settings.payment_provider)
    if provider_cls is None:
        raise AppError(
            "Configured payment provider is not available.",
            code="payment_provider_unknown",
            status_code=503,
        )
    return provider_cls()
