"""Tests for application page endpoints."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.routes.events import get_db
from app.main import app


@pytest.fixture
def client():
    """Create a test client without a real database connection."""
    app.dependency_overrides[get_db] = lambda: None

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("portal", "expected_ready"),
    [
        (None, False),
        (SimpleNamespace(is_active=False, installation_ready=True), False),
        (SimpleNamespace(is_active=True, installation_ready=False), False),
        (SimpleNamespace(is_active=True, installation_ready=True), True),
    ],
    ids=[
        "portal-not-found",
        "portal-inactive",
        "installation-not-ready",
        "installation-ready",
    ],
)
def test_installation_status(client, monkeypatch, portal, expected_ready):
    """Return the correct installation readiness status."""
    service = Mock()
    service.get_by_member_id.return_value = portal

    monkeypatch.setattr(
        "app.api.routes.pages.PortalService",
        lambda db: service,
    )

    response = client.get(
        "/install/status",
        params={"member_id": "test-member-id"},
    )

    assert response.status_code == 200
    assert response.json() == {"ready": expected_ready}
    service.get_by_member_id.assert_called_once_with("test-member-id")
