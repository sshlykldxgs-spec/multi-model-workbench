import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def admin_client(client: TestClient) -> TestClient:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin12345"},
    )
    assert resp.status_code == 200, resp.text
    return client
