import os
import sys
import asyncio
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure test environment before importing config/app
TEST_DB_PATH = str(backend_dir / "test_rop_database.db")
os.environ["DATABASE_PATH"] = TEST_DB_PATH
os.environ["ROP_ENV"] = "test"

from config import get_settings
from database import init_database, seed_demo_user
from main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create test database schema and demo user, and clean up afterwards."""
    settings = get_settings()
    settings.DATABASE_PATH = TEST_DB_PATH

    # Initialize schema and seed demo user
    asyncio.run(init_database())
    asyncio.run(seed_demo_user())

    yield

    # Clean up test database
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


@pytest.fixture(scope="module")
def client():
    """TestClient instance for FastAPI application."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    """Obtain a valid JWT token for authenticated requests."""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "rop2024"},
    )
    assert response.status_code == 200, f"Auth setup failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

