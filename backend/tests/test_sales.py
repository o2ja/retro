"""A request becomes a sale: the order, the stock and the payment stay in step."""

from fastapi.testclient import TestClient


def _request(
    client: TestClient, admin_client: TestClient, product_id: int, name: str
) -> dict:
    form = {
        "full_name": name,
        "email": f"{name.split()[0].lower()}@example.com",
        "phone": "+971 50 000 0000",
        "product_id": product_id,
    }
    assert client.post("/api/public/inquiries", json=form).status_code == 201
    listing = admin_client.get("/api/admin/inquiries?status=NEW").json()["items"]
    return next(i for i in listing if i["full_name"] == name)


def _stock(admin_client: TestClient, product_id: int) -> int:
    return admin_client.get(f"/api/admin/products/{product_id}").json()["stock_quantity"]


def test_request_to_paid_and_delivered(
    client: TestClient, admin_client: TestClient, created_product: dict
) -> None:
    pid = created_product["id"]
    inquiry = _request(client, admin_client, pid, "Omar Haddad")
    stock_before = _stock(admin_client, pid)

    # "Sold" can't be picked by hand; it comes from recording the sale.
    assert (
        admin_client.patch(
            f"/api/admin/inquiries/{inquiry['id']}", json={"status": "SOLD"}
        ).status_code
        == 409
    )

    sold = admin_client.post(
        f"/api/admin/inquiries/{inquiry['id']}/sale", json={"price": "1400.00"}
    )
    assert sold.status_code == 201, sold.text
    order_number = sold.json()["order_number"]
    assert sold.json()["status"] == "SOLD"
    assert _stock(admin_client, pid) == stock_before - 1

    order = admin_client.get(f"/api/admin/orders/{order_number}").json()
    assert (order["payment_status"], order["order_status"]) == (
        "PENDING",
        "PENDING_PAYMENT",
    )
    assert order["total"] == "1400.00"

    # Paid only through a recorded payment, never by picking a status.
    assert (
        admin_client.patch(
            f"/api/admin/orders/{order_number}/status",
            json={"order_status": "PAYMENT_CONFIRMED"},
        ).status_code
        == 409
    )
    paid = admin_client.post(
        f"/api/admin/orders/{order_number}/payments", json={"method": "cash"}
    ).json()
    assert (paid["payment_status"], paid["order_status"]) == ("PAID", "PAYMENT_CONFIRMED")
    assert (
        admin_client.post(
            f"/api/admin/orders/{order_number}/payments", json={"method": "cash"}
        ).status_code
        == 409
    )

    # Handed over in person: straight to delivered.
    delivered = admin_client.patch(
        f"/api/admin/orders/{order_number}/status", json={"order_status": "DELIVERED"}
    )
    assert delivered.json()["order_status"] == "DELIVERED"

    # A sold request can't be edited back.
    assert (
        admin_client.patch(
            f"/api/admin/inquiries/{inquiry['id']}", json={"status": "CLOSED"}
        ).status_code
        == 409
    )


def test_cancelled_sale_restocks_and_reopens(
    client: TestClient, admin_client: TestClient, created_product: dict
) -> None:
    pid = created_product["id"]
    inquiry = _request(client, admin_client, pid, "Lina Saad")
    stock_before = _stock(admin_client, pid)

    sold = admin_client.post(
        f"/api/admin/inquiries/{inquiry['id']}/sale",
        json={"price": "1500.00", "payment": {"method": "bank_transfer"}},
    ).json()
    order = admin_client.get(f"/api/admin/orders/{sold['order_number']}").json()
    assert order["payment_status"] == "PAID"

    admin_client.patch(
        f"/api/admin/orders/{sold['order_number']}/status",
        json={"order_status": "CANCELLED"},
    )
    assert _stock(admin_client, pid) == stock_before
    reopened = admin_client.get("/api/admin/inquiries?status=CONTACTED").json()["items"]
    match = next(i for i in reopened if i["id"] == inquiry["id"])
    assert match["order_number"] is None
