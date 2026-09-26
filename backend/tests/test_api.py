"""Phase 1 verification: auth, catalog, inventory, promotions, orders, CMS."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.enums import OrderStatus, PaymentStatus
from app.core.utils import generate_order_number
from app.db import SessionLocal, utcnow
from app.models import Order, OrderItem, Product
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


# --------------------------------------------------------------------------- #
# Admin authentication
# --------------------------------------------------------------------------- #


def test_admin_routes_require_authentication(client: TestClient) -> None:
    assert client.get("/api/admin/products").status_code == 401
    assert client.get("/api/admin/orders").status_code == 401
    assert client.patch("/api/admin/settings", json={}).status_code == 401


def test_login_rejects_wrong_password_generically(client: TestClient) -> None:
    response = client.post(
        "/api/admin/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"}
    )
    assert response.status_code == 401
    # Same message for unknown account and wrong password: no enumeration.
    assert response.json()["error"]["message"] == "Invalid email or password."

    unknown = client.post(
        "/api/admin/login", json={"email": "nobody@example.com", "password": "x"}
    )
    assert unknown.json()["error"]["message"] == "Invalid email or password."


def test_login_succeeds_and_sets_httponly_cookie(client: TestClient) -> None:
    response = client.post(
        "/api/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL
    assert "password" not in response.text.lower()

    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header

    assert client.get("/api/admin/me").status_code == 200
    client.post("/api/admin/logout")
    assert client.get("/api/admin/me").status_code == 401


def test_login_is_rate_limited(client: TestClient) -> None:
    payload = {"email": ADMIN_EMAIL, "password": "wrong-password"}
    statuses = [
        client.post("/api/admin/login", json=payload).status_code for _ in range(7)
    ]
    assert 429 in statuses, statuses


# --------------------------------------------------------------------------- #
# Public catalog
# --------------------------------------------------------------------------- #


def test_public_catalog_returns_seeded_products(client: TestClient) -> None:
    body = client.get("/api/public/products", params={"page_size": 20}).json()
    assert body["total"] == 9
    slugs = {item["slug"] for item in body["items"]}
    assert "rolex-submariner-date-kermit" in slugs


def test_catalog_search_brand_and_category_filters(client: TestClient) -> None:
    assert (
        client.get("/api/public/products", params={"q": "submariner"}).json()["total"]
        == 2
    )
    assert (
        client.get("/api/public/products", params={"brand": "rolex"}).json()["total"] == 4
    )
    assert (
        client.get("/api/public/products", params={"category": "diver"}).json()["total"]
        == 3
    )
    assert (
        client.get("/api/public/products", params={"q": "nothing-here"}).json()["total"]
        == 0
    )


def test_catalog_in_stock_filter_uses_inventory(client: TestClient) -> None:
    body = client.get("/api/public/products", params={"in_stock": True}).json()
    assert body["total"] == 2
    assert all(i["availability"] == "IN_STOCK" for i in body["items"])


def test_catalog_pagination(client: TestClient) -> None:
    first = client.get("/api/public/products", params={"page_size": 4, "page": 1}).json()
    second = client.get("/api/public/products", params={"page_size": 4, "page": 2}).json()
    assert len(first["items"]) == 4
    assert first["total"] == second["total"] == 9
    assert {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]} == set()


def test_sold_products_report_sold_not_deleted(client: TestClient) -> None:
    detail = client.get("/api/public/products/hublot-big-bang-unico").json()
    assert detail["availability"] == "SOLD"
    assert detail["stock_quantity"] == 0


def test_seeded_product_is_listed(client: TestClient) -> None:
    """Listed price and market value stay separate columns, both reported."""
    detail = client.get("/api/public/products/rolex-submariner-date-kermit").json()
    assert detail["pricing"]["price"] == "20000.00"
    assert detail["pricing"]["estimated_market_price"] == "20000.00"
    assert detail["pricing"]["price_on_request"] is False
    assert detail["specifications"]["case_size"] == "41mm"
    assert detail["related"]


def test_seed_photography_follows_its_switch(client: TestClient) -> None:
    """With app.seed.ATTACH_PHOTOGRAPHY on, each watch leads with its editorial
    photograph; off, listings carry no image and the storefront shows a placeholder."""
    from app.seed import ATTACH_PHOTOGRAPHY

    detail = client.get("/api/public/products/rolex-submariner-date-kermit").json()
    if ATTACH_PHOTOGRAPHY:
        assert detail["primary_image"]["url"].startswith("/watches/")
        assert [i["url"][:10] for i in detail["images"]] == ["/watches/r", "/products/"]
    else:
        assert detail["primary_image"] is None
        assert detail["images"] == []


def test_a_product_with_no_price_is_price_on_request(admin_client: TestClient) -> None:
    """Clearing a price must never fall back to the market value."""
    created = admin_client.post(
        "/api/admin/products",
        json={"name": "Unpriced Piece", "sku": "TEST-UNPRICED", "active": True},
    ).json()
    detail = admin_client.get("/api/public/products/unpriced-piece").json()
    assert detail["pricing"]["price"] is None
    assert detail["pricing"]["price_on_request"] is True
    admin_client.delete(f"/api/admin/products/{created['id']}")


def test_unknown_product_returns_clean_404(client: TestClient) -> None:
    response = client.get("/api/public/products/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_invalid_query_parameters_are_rejected(client: TestClient) -> None:
    assert client.get("/api/public/products", params={"page": 0}).status_code == 422
    assert (
        client.get("/api/public/products", params={"sort": "cheapest"}).status_code == 422
    )


# --------------------------------------------------------------------------- #
# Admin product CRUD + inventory
# --------------------------------------------------------------------------- #


def test_admin_can_create_update_and_price_a_product(
    admin_client: TestClient, created_product: dict
) -> None:
    assert created_product["slug"] == "test-piece-alpha"
    assert created_product["stock_quantity"] == 5
    assert created_product["availability"] == "IN_STOCK"

    updated = admin_client.patch(
        f"/api/admin/products/{created_product['id']}",
        json={"price": "1400.00", "featured": True},
    )
    assert updated.status_code == 200
    assert updated.json()["price"] == "1400.00"

    public = admin_client.get("/api/public/products/test-piece-alpha").json()
    assert public["pricing"]["final_price"] == "1400.00"
    assert public["pricing"]["price_on_request"] is False


def test_duplicate_sku_is_rejected(
    admin_client: TestClient, created_product: dict
) -> None:
    response = admin_client.post(
        "/api/admin/products", json={"name": "Clash", "sku": "TEST-ALPHA-1"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_inactive_product_is_hidden_from_the_storefront(
    admin_client: TestClient, created_product: dict
) -> None:
    admin_client.patch(
        f"/api/admin/products/{created_product['id']}", json={"active": False}
    )
    assert admin_client.get("/api/public/products/test-piece-alpha").status_code == 404
    admin_client.patch(
        f"/api/admin/products/{created_product['id']}", json={"active": True}
    )


def test_inventory_adjust_set_and_history(
    admin_client: TestClient, created_product: dict
) -> None:
    product_id = created_product["id"]

    adjusted = admin_client.post(
        f"/api/admin/products/{product_id}/inventory/adjust",
        json={"change": -2, "reason": "MANUAL_ADJUSTMENT"},
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["quantity"] == 3

    put = admin_client.put(
        f"/api/admin/products/{product_id}/inventory",
        json={"quantity": 1, "low_stock_threshold": 2},
    )
    assert put.json()["quantity"] == 1
    assert put.json()["availability"] == "LOW_STOCK"

    history = admin_client.get(
        f"/api/admin/products/{product_id}/inventory/history"
    ).json()
    assert [h["quantity_after"] for h in history] == [1, 3, 5]
    assert history[-1]["reason"] == "INITIAL_STOCK"


def test_inventory_cannot_go_negative(
    admin_client: TestClient, created_product: dict
) -> None:
    response = admin_client.post(
        f"/api/admin/products/{created_product['id']}/inventory/adjust",
        json={"change": -999, "reason": "ORDER_CONFIRMED"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"


def test_unique_pieces_are_not_reported_as_low_stock(admin_client: TestClient) -> None:
    low_stock = admin_client.get("/api/admin/inventory/low-stock").json()
    assert all(item["is_unique"] is False for item in low_stock)


def test_product_delete_is_hard_only_when_unreferenced(admin_client: TestClient) -> None:
    created = admin_client.post(
        "/api/admin/products", json={"name": "Disposable", "sku": "TEST-DISPOSABLE"}
    ).json()
    response = admin_client.delete(f"/api/admin/products/{created['id']}")
    assert response.json()["message"] == "Product deleted."
    assert admin_client.get(f"/api/admin/products/{created['id']}").status_code == 404


# --------------------------------------------------------------------------- #
# Brands & categories
# --------------------------------------------------------------------------- #


def test_brand_with_products_cannot_be_deleted(admin_client: TestClient) -> None:
    brands = admin_client.get("/api/admin/brands").json()
    rolex = next(b for b in brands if b["slug"] == "rolex")
    assert rolex["product_count"] == 4
    response = admin_client.delete(f"/api/admin/brands/{rolex['id']}")
    assert response.status_code == 409


def test_category_crud(admin_client: TestClient) -> None:
    created = admin_client.post("/api/admin/categories", json={"name": "Test Collection"})
    assert created.status_code == 201
    category_id = created.json()["id"]
    assert created.json()["slug"] == "test-collection"

    admin_client.patch(f"/api/admin/categories/{category_id}", json={"active": False})
    public_slugs = {c["slug"] for c in admin_client.get("/api/public/categories").json()}
    assert "test-collection" not in public_slugs

    assert admin_client.delete(f"/api/admin/categories/{category_id}").status_code == 200


# --------------------------------------------------------------------------- #
# Promotions
# --------------------------------------------------------------------------- #


def test_promotion_validation_is_server_side(
    admin_client: TestClient, created_product: dict
) -> None:
    created = admin_client.post(
        "/api/admin/promotions",
        json={
            "name": "Test Code",
            "code": "welcome10",
            "discount_type": "PERCENTAGE",
            "discount_value": "10",
            "minimum_order_value": "1000",
        },
    )
    assert created.status_code == 201
    assert created.json()["code"] == "WELCOME10"

    valid = admin_client.post(
        "/api/public/promotions/check", json={"code": "welcome10", "subtotal": "2000.00"}
    ).json()
    assert valid == {
        "valid": True,
        "code": "WELCOME10",
        "name": "Test Code",
        "discount_amount": "200.00",
        "new_total": "1800.00",
    }

    below_minimum = admin_client.post(
        "/api/public/promotions/check", json={"code": "welcome10", "subtotal": "500.00"}
    )
    assert below_minimum.status_code == 400
    assert below_minimum.json()["error"]["code"] == "promotion_minimum_not_met"

    unknown = admin_client.post(
        "/api/public/promotions/check", json={"code": "not-a-code", "subtotal": "500.00"}
    )
    assert unknown.json()["error"]["code"] == "invalid_promotion"

    # Deactivated codes stop working immediately.
    admin_client.delete(f"/api/admin/promotions/{created.json()['id']}")
    after = admin_client.post(
        "/api/public/promotions/check", json={"code": "welcome10", "subtotal": "2000.00"}
    )
    assert after.json()["error"]["code"] == "invalid_promotion"


def test_percentage_over_100_is_rejected(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/api/admin/promotions",
        json={
            "name": "Impossible",
            "discount_type": "PERCENTAGE",
            "discount_value": "150",
        },
    )
    assert response.status_code == 422
    assert "100" in response.text


def test_automatic_promotion_discounts_the_storefront_price(
    admin_client: TestClient, created_product: dict
) -> None:
    admin_client.patch(
        f"/api/admin/products/{created_product['id']}", json={"price": "1000.00"}
    )
    promotion = admin_client.post(
        "/api/admin/promotions",
        json={
            "name": "Automatic 20",
            "discount_type": "PERCENTAGE",
            "discount_value": "20",
            "product_ids": [created_product["id"]],
        },
    )
    assert promotion.status_code == 201

    detail = admin_client.get("/api/public/products/test-piece-alpha").json()
    assert detail["pricing"]["final_price"] == "800.00"
    assert detail["pricing"]["promotion_name"] == "Automatic 20"

    offers = admin_client.get("/api/public/offers").json()
    assert any(o["name"] == "Automatic 20" for o in offers)

    admin_client.delete(f"/api/admin/promotions/{promotion.json()['id']}")


# --------------------------------------------------------------------------- #
# Orders (status workflow; creation belongs to the verified-payment flow)
# --------------------------------------------------------------------------- #


@pytest.fixture
def paid_order(created_product: dict) -> str:
    """An order written straight to the database, as the payment flow will do."""
    with SessionLocal() as db:
        product = db.get(Product, created_product["id"])
        order = Order(
            order_number=generate_order_number(utcnow()),
            subtotal=Decimal("1400.00"),
            discount_total=Decimal("0.00"),
            shipping_total=Decimal("0.00"),
            total=Decimal("1400.00"),
            currency="USD",
            payment_status=PaymentStatus.PAID,
            order_status=OrderStatus.PAYMENT_CONFIRMED,
            shipping_name="Test Buyer",
            shipping_email="buyer@example.com",
            shipping_address="1 Example Street",
            shipping_city="Baghdad",
            shipping_country="Iraq",
        )
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name_snapshot=product.name,
                sku_snapshot=product.sku,
                unit_price=Decimal("1400.00"),
                quantity=1,
                discount_amount=Decimal("0.00"),
                line_total=Decimal("1400.00"),
            )
        )
        db.add(order)
        db.commit()
        return order.order_number


def test_order_status_transitions_are_validated(
    admin_client: TestClient, paid_order: str
) -> None:
    invalid = admin_client.patch(
        f"/api/admin/orders/{paid_order}/status", json={"order_status": "SHIPPED"}
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_status_transition"

    ok = admin_client.patch(
        f"/api/admin/orders/{paid_order}/status", json={"order_status": "PROCESSING"}
    )
    assert ok.status_code == 200
    assert ok.json()["order_status"] == "PROCESSING"
    assert [h["to_status"] for h in ok.json()["status_history"]] == ["PROCESSING"]


def test_cancelling_a_confirmed_order_restores_inventory(
    admin_client: TestClient, paid_order: str, created_product: dict
) -> None:
    before = admin_client.get(
        f"/api/admin/products/{created_product['id']}/inventory"
    ).json()["quantity"]

    cancelled = admin_client.patch(
        f"/api/admin/orders/{paid_order}/status",
        json={"order_status": "CANCELLED", "note": "Customer request"},
    )
    assert cancelled.status_code == 200

    after = admin_client.get(
        f"/api/admin/products/{created_product['id']}/inventory"
    ).json()["quantity"]
    assert after == before + 1


def test_order_items_keep_a_purchase_snapshot(
    admin_client: TestClient, paid_order: str, created_product: dict
) -> None:
    admin_client.patch(
        f"/api/admin/products/{created_product['id']}", json={"name": "Renamed Later"}
    )
    order = admin_client.get(f"/api/admin/orders/{paid_order}").json()
    assert order["items"][0]["product_name_snapshot"] == "Test Piece Alpha"
    assert order["items"][0]["unit_price"] == "1400.00"


# --------------------------------------------------------------------------- #
# Content, CMS and settings
# --------------------------------------------------------------------------- #


def test_only_published_posts_are_public(admin_client: TestClient) -> None:
    public = admin_client.get("/api/public/posts").json()
    assert public["total"] == 1
    assert (
        admin_client.get("/api/public/posts/caring-for-an-automatic-watch").status_code
        == 404
    )

    drafts = admin_client.get("/api/admin/posts", params={"post_status": "DRAFT"}).json()
    draft_id = drafts["items"][0]["id"]
    admin_client.patch(f"/api/admin/posts/{draft_id}", json={"status": "PUBLISHED"})

    assert admin_client.get("/api/public/posts").json()["total"] == 2
    assert (
        admin_client.get("/api/public/posts/caring-for-an-automatic-watch").status_code
        == 200
    )


def test_homepage_is_cms_driven(admin_client: TestClient) -> None:
    admin_client.put(
        "/api/admin/homepage/sections",
        json={
            "section_type": "HERO",
            "title": "A New Hero Title",
            "subtitle": "Set from the dashboard",
            "cta_label": "Shop",
            "cta_url": "/shop",
            "visible": True,
            "sort_order": 0,
        },
    )
    homepage = admin_client.get("/api/public/homepage").json()
    hero = next(s for s in homepage["sections"] if s["section_type"] == "HERO")
    assert hero["title"] == "A New Hero Title"
    assert len(homepage["featured_products"]) >= 1


def test_settings_and_social_links_drive_the_public_api(admin_client: TestClient) -> None:
    admin_client.patch(
        "/api/admin/settings", json={"contact_email": "hello@obaiditime.com"}
    )
    settings_body = admin_client.get("/api/public/settings").json()
    assert settings_body["brand_name"] == "Retro Watches"
    assert settings_body["contact_email"] == "hello@obaiditime.com"

    links = admin_client.get("/api/public/social-links").json()
    assert links[0]["platform"] == "instagram"
    assert "retrowatches.jo" in links[0]["url"]


def test_settings_reject_unknown_fields(admin_client: TestClient) -> None:
    """Payment secrets must never be settable through the CMS."""
    response = admin_client.patch(
        "/api/admin/settings", json={"payment_secret_key": "sk_live_123"}
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #


def test_no_payment_provider_is_configured_yet() -> None:
    """Phase 1 ships the abstraction only; nothing can mark a payment as paid."""
    from app.core.errors import AppError
    from app.payments import get_provider

    provider = get_provider()
    with pytest.raises(AppError) as excinfo:
        provider.verify_payment("anything")
    assert excinfo.value.code == "payment_provider_unconfigured"


# --------------------------------------------------------------------------- #
# Checkout (server-authoritative totals; no order is created)
# --------------------------------------------------------------------------- #


def test_quote_is_calculated_server_side(
    admin_client: TestClient, created_product: dict
) -> None:
    admin_client.patch(
        f"/api/admin/products/{created_product['id']}", json={"price": "1000.00"}
    )
    admin_client.put(
        f"/api/admin/products/{created_product['id']}/inventory",
        json={"quantity": 5, "low_stock_threshold": 2},
    )
    body = admin_client.post(
        "/api/checkout/quote",
        json={"items": [{"product_id": created_product["id"], "quantity": 2}]},
    ).json()
    assert body["subtotal"] == "2000.00"
    assert body["total"] == "2000.00"
    assert body["is_payable"] is True
    assert body["lines"][0]["unit_price"] == "1000.00"


def test_quote_refuses_more_than_is_in_stock(
    admin_client: TestClient, created_product: dict
) -> None:
    body = admin_client.post(
        "/api/checkout/quote",
        json={"items": [{"product_id": created_product["id"], "quantity": 9}]},
    ).json()
    assert body["is_payable"] is False
    assert body["issues"][0]["code"] == "insufficient_stock"
    assert body["lines"] == []


def test_quote_reports_sold_and_unknown_items(admin_client: TestClient) -> None:
    sold = admin_client.get("/api/public/products/hublot-big-bang-unico").json()
    body = admin_client.post(
        "/api/checkout/quote",
        json={
            "items": [
                {"product_id": sold["id"], "quantity": 1},
                {"product_id": 999999, "quantity": 1},
            ]
        },
    ).json()
    codes = {issue["code"] for issue in body["issues"]}
    assert codes == {"insufficient_stock", "unavailable"}
    assert body["is_payable"] is False


def test_quote_applies_a_valid_promotion_code(
    admin_client: TestClient, created_product: dict
) -> None:
    promotion = admin_client.post(
        "/api/admin/promotions",
        json={
            "name": "Checkout Ten",
            "code": "CHECKOUT10",
            "discount_type": "PERCENTAGE",
            "discount_value": "10",
        },
    )
    assert promotion.status_code == 201
    body = admin_client.post(
        "/api/checkout/quote",
        json={
            "items": [{"product_id": created_product["id"], "quantity": 1}],
            "promotion_code": "checkout10",
        },
    ).json()
    assert body["subtotal"] == "1000.00"
    assert body["discount_total"] == "100.00"
    assert body["total"] == "900.00"
    assert body["promotion_code"] == "CHECKOUT10"
    admin_client.delete(f"/api/admin/promotions/{promotion.json()['id']}")


def test_client_cannot_send_its_own_prices(
    admin_client: TestClient, created_product: dict
) -> None:
    """Extra money fields are ignored - the schema only accepts id and quantity."""
    body = admin_client.post(
        "/api/checkout/quote",
        json={
            "items": [
                {
                    "product_id": created_product["id"],
                    "quantity": 1,
                    "unit_price": "1.00",
                    "line_total": "1.00",
                }
            ],
            "subtotal": "1.00",
            "total": "1.00",
        },
    ).json()
    assert body["total"] == "1000.00"


def test_payment_session_refuses_until_a_provider_exists(
    admin_client: TestClient, created_product: dict
) -> None:
    """Phase 2 wires the UI to a real endpoint; it cannot fake a payment."""
    response = admin_client.post(
        "/api/checkout/payment-session",
        json={
            "items": [{"product_id": created_product["id"], "quantity": 1}],
            "shipping": {
                "full_name": "Test Buyer",
                "email": "buyer@example.com",
                "address": "1 Example Street",
                "city": "Baghdad",
                "country": "Iraq",
            },
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "payment_provider_unconfigured"


def test_payment_session_refuses_an_unpayable_cart(admin_client: TestClient) -> None:
    sold = admin_client.get("/api/public/products/rolex-sea-dweller").json()
    response = admin_client.post(
        "/api/checkout/payment-session",
        json={
            "items": [{"product_id": sold["id"], "quantity": 1}],
            "shipping": {
                "full_name": "Test Buyer",
                "email": "buyer@example.com",
                "address": "1 Example Street",
                "city": "Baghdad",
                "country": "Iraq",
            },
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cart_not_payable"
