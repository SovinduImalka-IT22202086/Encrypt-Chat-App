"""Phase 1 infrastructure smoke tests.

These verify that the development environment works (imports, ASGI app,
pytest configuration). They are NOT tests of application functionality —
no Phase 2+ functionality exists to test.
"""

from fastapi.testclient import TestClient

from app import __version__
from app.main import app


def test_package_imports() -> None:
    """The application package imports and exposes a version."""
    assert __version__ == "0.1.0"


def test_app_instance_is_constructed() -> None:
    """The FastAPI application object is constructed at import time."""
    assert app.title == "Encrypted Chat Application (development scaffold)"
    assert app.version == __version__


def test_health_endpoint_returns_expected_payload() -> None:
    """The health endpoint responds with the static development payload."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "phase": "1",
        "encrypted_messaging": "not_implemented",
    }


def test_health_endpoint_exposes_no_sensitive_fields() -> None:
    """SERVER-008: the health payload must not leak configuration or secrets.

    This is a guard test: it fails if a future change adds fields to the
    health response without a deliberate review of what is being exposed.
    """
    with TestClient(app) as client:
        payload = client.get("/health").json()

    assert set(payload) == {"status", "phase", "encrypted_messaging"}
