"""Phase 4: payments, order creation, inventory safety, analytics.

A fake provider stands in for Stripe so the whole flow is exercised without a
network call. The Stripe signature check itself is tested directly against the
real verifier.
"""

import json
import time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.enums import PaymentStatus
from app.core.errors import AppError
from app.db import SessionLocal
from app.models import Inventory, Order, Payment, Product
from app.payments.base import PaymentSession, PaymentVerification

PROVIDER = "fake"


class FakeProvider:
    """Deterministic stand-in. `outcome` decides what the provider "says"."""

    name = PROVIDER
    outcome = PaymentStatus.PAID
    amount_override: Decimal | None = None
    currency_override: str | None = None
    last_amount = Decimal("0")

    def create_session(
        self, *, order_number, amount, currency, customer_email, return_url
    ):  # noqa: ANN001, ANN201
        FakeProvider.last_amount = amount
        return PaymentSession(
            provider=PROVIDER,
            provider_payment_id=f"sess_{order_number}",
            redirect_url=f"https://pay.example/{order_number}",
        )

    def verify_payment(self, provider_payment_id: str) -> PaymentVerification:
        return PaymentVerification(
            provider_payment_id=provider_payment_id,
            status=FakeProvider.outcome,
            amount=FakeProvider.amount_override or FakeProvider.last_amount,
            currency=FakeProvider.currency_override or "USD",
        )

    def parse_webhook(self, payload: bytes, headers: dict) -> PaymentVerification:
        body = json.loads(payload)
        return PaymentVerification(
            provider_payment_id=body["id"],
            status=PaymentStatus(body["status"]),
            amount=Decimal(body["amount"]),
            currency=body.get("currency", "USD"),
            provider_event_id=body.get("event_id"),
        )

    def refund(self, provider_payment_id: str, amount: Decimal) -> PaymentVerification:
        return PaymentVerification(
            provider_payment_id=provider_payment_id,
            status=PaymentStatus.REFUNDED,
            amount=amount,
            currency="USD",
        )


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):  # noqa: ANN001, ANN201
    """Point the whole app at the fake provider for these tests."""
    from app.core import ratelimit
    from app.core.config import settings

    # Payment sessions are rate limited per IP; every test here shares one IP.
    ratelimit.reset()

    monkeypatch.setattr(settings, "payment_provider", PROVIDER, raising=False)
    monkeypatch.setattr(
        "app.payments._registry",
        lambda: {PROVIDER: FakeProvider},
        raising=False,
    )
    FakeProvider.outcome = PaymentStatus.PAID
    FakeProvider.amount_override = None
    FakeProvider.currency_override = None
    yield


SHIPPING = {
    "full_name": "Test Buyer",
    "email": "buyer@example.com",
    "address": "1 Example Street",
    "city": "Baghdad",
    "country": "Iraq",
}


@pytest.fixture
def sellable(admin_client: TestClient) -> dict:
    """A fresh, priced, in-stock product for each test."""
    import uuid

    sku = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    product = admin_client.post(
        "/api/admin/products",
        json={
            "name": f"Payment Test {sku}",
            "sku": sku,
            "price": "1000.00",
            "is_unique": False,
            "stock_quantity": 2,
            "active": True,
        },
    ).json()
    return product


def start_payment(client: TestClient, product_id: int, quantity: int = 1):  # noqa: ANN201
    return client.post(
        "/api/checkout/payment-session",
        json={
            "items": [{"product_id": product_id, "quantity": quantity}],
            "shipping": SHIPPING,
        },
    )


def webhook(client: TestClient, session_id: str, amount: str, **extra):  # noqa: ANN201
    body = {"id": session_id, "status": "PAID", "amount": amount, **extra}
    return client.post(f"/api/payments/webhook/{PROVIDER}", json=body)


def stock_of(product_id: int) -> int:
    with SessionLocal() as db:
        record = db.query(Inventory).filter_by(product_id=product_id).one()
        return record.quantity


# --------------------------------------------------------------------------- #
# Order creation and the stock hold
# --------------------------------------------------------------------------- #


def test_payment_session_opens_a_pending_order_and_holds_stock(
    admin_client: TestClient, sellable: dict
) -> None:
    before = stock_of(sellable["id"])
    response = start_payment(admin_client, sellable["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["redirect_url"].startswith("https://pay.example/")
    assert body["total"] == "1000.00"

    order = admin_client.get(f"/api/admin/orders/{body['order_number']}").json()
    assert order["order_status"] == "PENDING_PAYMENT"
    assert order["payment_status"] == "PENDING"
    # Stock is held immediately - that is what stops two people buying one watch.
    assert stock_of(sellable["id"]) == before - 1


def test_order_is_only_paid_after_a_verified_webhook(
    admin_client: TestClient, sellable: dict
) -> None:
    session = start_payment(admin_client, sellable["id"]).json()
    order_number = session["order_number"]

    assert (
        webhook(admin_client, session["provider_payment_id"], "1000.00").status_code
        == 200
    )

    order = admin_client.get(f"/api/admin/orders/{order_number}").json()
    assert order["payment_status"] == "PAID"
    assert order["order_status"] == "PAYMENT_CONFIRMED"
    assert [h["to_status"] for h in order["status_history"]] == ["PAYMENT_CONFIRMED"]


def test_duplicate_webhook_does_not_decrement_stock_twice(
    admin_client: TestClient, sellable: dict
) -> None:
    before = stock_of(sellable["id"])
    session = start_payment(admin_client, sellable["id"]).json()
    reference = session["provider_payment_id"]

    first = webhook(admin_client, reference, "1000.00", event_id="evt_1")
    second = webhook(admin_client, reference, "1000.00", event_id="evt_1")
    third = webhook(admin_client, reference, "1000.00", event_id="evt_1")

    assert first.json()["message"] == "Processed"
    assert second.json()["message"] == "Already processed"
    assert third.json()["message"] == "Already processed"
    assert stock_of(sellable["id"]) == before - 1

    with SessionLocal() as db:
        order = db.query(Order).filter_by(order_number=session["order_number"]).one()
        assert len(order.payments) == 1


def test_wrong_amount_is_rejected(admin_client: TestClient, sellable: dict) -> None:
    session = start_payment(admin_client, sellable["id"]).json()
    response = webhook(admin_client, session["provider_payment_id"], "1.00")
    assert response.status_code == 409
    order = admin_client.get(f"/api/admin/orders/{session['order_number']}").json()
    assert order["payment_status"] == "PENDING"


def test_wrong_currency_is_rejected(admin_client: TestClient, sellable: dict) -> None:
    session = start_payment(admin_client, sellable["id"]).json()
    response = admin_client.post(
        f"/api/payments/webhook/{PROVIDER}",
        json={
            "id": session["provider_payment_id"],
            "status": "PAID",
            "amount": "1000.00",
            "currency": "EUR",
        },
    )
    assert response.status_code == 409


def test_failed_payment_cancels_the_order_and_returns_stock(
    admin_client: TestClient, sellable: dict
) -> None:
    before = stock_of(sellable["id"])
    session = start_payment(admin_client, sellable["id"]).json()
    assert stock_of(sellable["id"]) == before - 1

    response = admin_client.post(
        f"/api/payments/webhook/{PROVIDER}",
        json={
            "id": session["provider_payment_id"],
            "status": "FAILED",
            "amount": "1000.00",
        },
    )
    assert response.status_code == 200

    order = admin_client.get(f"/api/admin/orders/{session['order_number']}").json()
    assert order["payment_status"] == "FAILED"
    assert order["order_status"] == "CANCELLED"
    assert stock_of(sellable["id"]) == before


def test_cannot_oversell_the_last_piece(admin_client: TestClient) -> None:
    """Two checkouts for one unit: the second is refused, not oversold."""
    only_one = admin_client.post(
        "/api/admin/products",
        json={
            "name": "One Of One",
            "sku": "PAY-ONLYONE",
            "price": "500.00",
            "is_unique": False,
            "stock_quantity": 1,
            "active": True,
        },
    ).json()

    first = start_payment(admin_client, only_one["id"])
    assert first.status_code == 200
    assert stock_of(only_one["id"]) == 0

    second = start_payment(admin_client, only_one["id"])
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "cart_not_payable"
    assert stock_of(only_one["id"]) == 0


def test_admin_cancelling_a_pending_order_returns_stock(
    admin_client: TestClient, sellable: dict
) -> None:
    before = stock_of(sellable["id"])
    session = start_payment(admin_client, sellable["id"]).json()
    assert stock_of(sellable["id"]) == before - 1

    admin_client.patch(
        f"/api/admin/orders/{session['order_number']}/status",
        json={"order_status": "CANCELLED", "note": "Customer changed their mind"},
    )
    assert stock_of(sellable["id"]) == before


# --------------------------------------------------------------------------- #
# Customer-facing order lookup
# --------------------------------------------------------------------------- #


def test_order_lookup_needs_the_matching_email(
    admin_client: TestClient, sellable: dict
) -> None:
    session = start_payment(admin_client, sellable["id"]).json()
    number = session["order_number"]
    webhook(admin_client, session["provider_payment_id"], "1000.00")

    assert (
        admin_client.get(f"/api/orders/{number}?email=wrong@example.com").status_code
        == 404
    )

    body = admin_client.get(f"/api/orders/{number}?email=buyer@example.com").json()
    assert body["order_number"] == number
    assert body["payment_status"] == "PAID"
    assert body["items"][0]["quantity"] == 1
    # No internal identifiers or provider references reach the customer.
    assert "provider_payment_id" not in json.dumps(body)
    assert "customer_id" not in body


def test_guest_checkout_creates_a_customer(
    admin_client: TestClient, sellable: dict
) -> None:
    session = start_payment(admin_client, sellable["id"]).json()
    webhook(admin_client, session["provider_payment_id"], "1000.00")

    customers = admin_client.get(
        "/api/admin/customers", params={"q": "buyer@example.com"}
    ).json()
    assert customers["total"] >= 1
    detail = admin_client.get(
        f"/api/admin/customers/{customers['items'][0]['id']}"
    ).json()
    assert Decimal(detail["total_spent"]) >= Decimal("1000.00")
    assert detail["order_count"] >= 1


# --------------------------------------------------------------------------- #
# Refunds
# --------------------------------------------------------------------------- #


def test_refund_marks_the_order_refunded_and_restores_stock(
    admin_client: TestClient, sellable: dict
) -> None:
    before = stock_of(sellable["id"])
    session = start_payment(admin_client, sellable["id"]).json()
    webhook(admin_client, session["provider_payment_id"], "1000.00")
    assert stock_of(sellable["id"]) == before - 1

    refunded = admin_client.post(
        f"/api/admin/orders/{session['order_number']}/refund",
        json={"reason": "Customer returned it"},
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["payment_status"] == "REFUNDED"
    assert refunded.json()["order_status"] == "REFUNDED"
    assert stock_of(sellable["id"]) == before


def test_unpaid_order_cannot_be_refunded(
    admin_client: TestClient, sellable: dict
) -> None:
    session = start_payment(admin_client, sellable["id"]).json()
    response = admin_client.post(
        f"/api/admin/orders/{session['order_number']}/refund", json={}
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# Stripe signature verification (the real verifier, no network)
# --------------------------------------------------------------------------- #


def _stripe_provider(monkeypatch):  # noqa: ANN001, ANN202
    from app.core.config import settings
    from app.payments.stripe import StripeProvider

    monkeypatch.setattr(settings, "payment_secret_key", "sk_test_x", raising=False)
    monkeypatch.setattr(settings, "payment_webhook_secret", "whsec_x", raising=False)
    return StripeProvider()


def test_stripe_accepts_a_correctly_signed_webhook(monkeypatch) -> None:  # noqa: ANN001
    from app.payments.stripe import sign_webhook

    provider = _stripe_provider(monkeypatch)
    payload = json.dumps(
        {
            "id": "evt_123",
            "data": {
                "object": {
                    "id": "cs_1",
                    "payment_status": "paid",
                    "amount_total": 250000,
                    "currency": "usd",
                }
            },
        }
    ).encode()
    header = sign_webhook(payload, "whsec_x")

    result = provider.parse_webhook(payload, {"stripe-signature": header})
    assert result.status is PaymentStatus.PAID
    assert result.amount == Decimal("2500.00")
    assert result.provider_event_id == "evt_123"


def test_stripe_rejects_a_forged_or_stale_signature(monkeypatch) -> None:  # noqa: ANN001
    from app.payments.stripe import sign_webhook

    provider = _stripe_provider(monkeypatch)
    payload = b'{"id":"evt_1","data":{"object":{}}}'

    with pytest.raises(AppError) as forged:
        provider.parse_webhook(payload, {"stripe-signature": "t=1,v1=deadbeef"})
    assert forged.value.code == "invalid_webhook"

    # Correctly signed, but far too old to accept.
    stale = sign_webhook(payload, "whsec_x", timestamp=int(time.time()) - 10_000)
    with pytest.raises(AppError) as expired:
        provider.parse_webhook(payload, {"stripe-signature": stale})
    assert expired.value.code == "invalid_webhook"

    # Signed with the wrong secret.
    wrong = sign_webhook(payload, "whsec_other")
    with pytest.raises(AppError):
        provider.parse_webhook(payload, {"stripe-signature": wrong})


def test_stripe_never_stores_card_data() -> None:
    """The Payment table has no column that could hold a card number."""
    columns = {c.name for c in Payment.__table__.columns}
    forbidden = {"card_number", "cvv", "cvc", "pan", "card", "expiry"}
    assert columns & forbidden == set()


# --------------------------------------------------------------------------- #
# Analytics on real data
# --------------------------------------------------------------------------- #


def test_dashboard_counts_only_paid_orders(
    admin_client: TestClient, sellable: dict
) -> None:
    baseline = admin_client.get("/api/admin/dashboard", params={"range": "month"}).json()
    start_revenue = Decimal(baseline["kpis"]["revenue"])
    start_orders = baseline["kpis"]["orders"]

    # An unpaid order must not move revenue.
    start_payment(admin_client, sellable["id"])
    unpaid = admin_client.get("/api/admin/dashboard", params={"range": "month"}).json()
    assert Decimal(unpaid["kpis"]["revenue"]) == start_revenue
    assert unpaid["kpis"]["orders"] == start_orders
    assert unpaid["kpis"]["pending_payments"] >= 1

    # A paid one must.
    session = start_payment(admin_client, sellable["id"]).json()
    webhook(admin_client, session["provider_payment_id"], "1000.00")

    after = admin_client.get("/api/admin/dashboard", params={"range": "month"}).json()
    assert Decimal(after["kpis"]["revenue"]) == start_revenue + Decimal("1000.00")
    assert after["kpis"]["orders"] == start_orders + 1
    assert Decimal(after["kpis"]["average_order_value"]) > 0
    assert any(
        row["label"].startswith("Payment Test") for row in after["best_selling_products"]
    )
    assert len(after["revenue_series"]) == after["range"]["days"]


def test_dashboard_empty_range_reports_zero_not_nothing(
    admin_client: TestClient,
) -> None:
    body = admin_client.get(
        "/api/admin/dashboard",
        params={
            "range": "custom",
            "start": "2020-01-01T00:00:00Z",
            "end": "2020-01-07T23:59:59Z",
        },
    ).json()
    assert Decimal(body["kpis"]["revenue"]) == Decimal("0")
    assert body["kpis"]["orders"] == 0
    assert body["best_selling_products"] == []
    # Seven days of explicit zeros, not an empty array.
    assert len(body["revenue_series"]) == 7
    assert all(Decimal(p["value"]) == 0 for p in body["revenue_series"])


def test_dashboard_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/admin/dashboard").status_code == 401


def test_full_lifecycle_pending_to_delivered(
    admin_client: TestClient, sellable: dict
) -> None:
    session = start_payment(admin_client, sellable["id"]).json()
    number = session["order_number"]
    webhook(admin_client, session["provider_payment_id"], "1000.00")

    for status in ("PROCESSING", "SHIPPED", "DELIVERED"):
        response = admin_client.patch(
            f"/api/admin/orders/{number}/status", json={"order_status": status}
        )
        assert response.status_code == 200, response.text

    order = admin_client.get(f"/api/admin/orders/{number}").json()
    assert order["order_status"] == "DELIVERED"
    assert [h["to_status"] for h in order["status_history"]] == [
        "PAYMENT_CONFIRMED",
        "PROCESSING",
        "SHIPPED",
        "DELIVERED",
    ]

    with SessionLocal() as db:
        product = db.get(Product, sellable["id"])
        stored = db.query(Order).filter_by(order_number=number).one()
        # The purchase snapshot survives a later rename.
        product.name = "Renamed After Sale"
        db.commit()
        assert stored.items[0].product_name_snapshot.startswith("Payment Test")
