"""The admin edit form round-trips every field, so saving never blanks one."""

from fastapi.testclient import TestClient


def test_admin_product_returns_every_editable_field(admin_client: TestClient) -> None:
    created = admin_client.post(
        "/api/admin/products",
        json={
            "name": "Form Round Trip",
            "sku": "FORM-RT-1",
            "description": "Serviced in 2025.",
            "movement": "Automatic",
            "condition": "EXCELLENT",
            "cutout_url": "/cutouts/form-round-trip.png",
        },
    ).json()

    loaded = admin_client.get(f"/api/admin/products/{created['id']}").json()
    assert loaded["description"] == "Serviced in 2025."
    assert loaded["movement"] == "Automatic"
    assert loaded["condition"] == "EXCELLENT"
    assert loaded["cutout_url"] == "/cutouts/form-round-trip.png"

    public = admin_client.get(f"/api/public/products/{created['slug']}").json()
    assert public["cutout_url"] == "/cutouts/form-round-trip.png"
