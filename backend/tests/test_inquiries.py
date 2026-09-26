"""The inquiry flow: a customer asks, the owner sees it and follows up."""

from fastapi.testclient import TestClient


def test_inquiry_round_trip(client: TestClient, admin_client: TestClient) -> None:
    product = client.get("/api/public/products?page_size=1").json()["items"][0]
    form = {
        "full_name": "  Sara Khan ",
        "email": "Sara@Example.com",
        "phone": "+971 50 123 4567",
        "product_id": product["id"],
        "message": "Is the box included?",
    }

    assert client.post("/api/public/inquiries", json=form).status_code == 201

    # Bad input and unknown watches are refused.
    assert (
        client.post(
            "/api/public/inquiries", json={**form, "phone": "call me"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/public/inquiries", json={**form, "product_id": 999999}
        ).status_code
        == 404
    )

    listing = admin_client.get("/api/admin/inquiries?status=NEW").json()
    inquiry = listing["items"][0]
    assert inquiry["full_name"] == "Sara Khan"
    assert inquiry["email"] == "sara@example.com"
    assert inquiry["product_name_snapshot"] == product["name"]

    updated = admin_client.patch(
        f"/api/admin/inquiries/{inquiry['id']}", json={"status": "CONTACTED"}
    )
    assert updated.json()["status"] == "CONTACTED"
    assert client.get("/api/admin/inquiries").status_code == 401
