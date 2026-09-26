"""Test harness: a throwaway SQLite database, migrated with Alembic and seeded."""

import os
import pathlib

# Must be set before app.core.config is imported anywhere.
TEST_DB = pathlib.Path(__file__).resolve().parent.parent / "test_obaidi_time.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["ENVIRONMENT"] = "development"
os.environ["ADMIN_EMAIL"] = "test-admin@retrowatches.jo"
os.environ["ADMIN_PASSWORD"] = "TestAdmin!2026"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from alembic import command  # noqa: E402
from app import seed  # noqa: E402
from app.core import ratelimit  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402

ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    """Fresh database, migrated through Alembic so migrations are tested too."""
    TEST_DB.unlink(missing_ok=True)
    root = pathlib.Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")
    seed.run()
    yield
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture
def client() -> TestClient:
    """Anonymous client with a clean rate-limit bucket."""
    ratelimit.reset()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_client() -> TestClient:
    """Signed-in admin, shared for the session so the login cookie is reused."""
    ratelimit.reset()
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, response.text
        yield test_client


@pytest.fixture(scope="session")
def created_product(admin_client: TestClient) -> dict:
    """One admin-created product, reused by the tests that need a priced item."""
    response = admin_client.post(
        "/api/admin/products",
        json={
            "name": "Test Piece Alpha",
            "sku": "TEST-ALPHA-1",
            "price": "1500.00",
            "compare_at_price": "1800.00",
            "is_unique": False,
            "stock_quantity": 5,
            "low_stock_threshold": 2,
            "active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
