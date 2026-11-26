"""Tests for Bitrix24 application event endpoints."""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.routes.events import get_db
from app.main import app
from app.services.event_service import InvalidApplicationToken


@pytest.fixture
def client():
    """Create a test client without a real database connection."""
    app.dependency_overrides[get_db] = lambda: None

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def installation_mocks(monkeypatch):
    """Mock services used by the installation event handler."""
    service = Mock()
    oauth_validate = AsyncMock()
    ensure_handler = AsyncMock(return_value=True)

    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventService",
        lambda db: service,
    )
    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24OAuthClient",
        lambda: Mock(validate_installation=oauth_validate),
    )
    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventClient.ensure_event_handler",
        ensure_handler,
    )
    monkeypatch.setattr(
        "app.api.routes.events.settings.bitrix24_event_handler_url",
        "https://example.com/events/bitrix24",
    )

    return service, oauth_validate, ensure_handler


def make_install_payload() -> dict:
    """Build a valid ONAPPINSTALL payload."""
    return {
        "event": "ONAPPINSTALL",
        "data": {
            "VERSION": "1",
            "LANGUAGE_ID": "ru",
        },
        "auth": {
            "domain": "test.bitrix24.ru",
            "member_id": "test-member-id",
            "application_token": "test-application-token",
            "client_endpoint": "https://test.bitrix24.ru/rest/",
            "server_endpoint": "https://oauth.bitrix24.tech/rest/",
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600,
            "scope": "crm",
        },
        "ts": 1730000000,
    }


def make_uninstall_payload() -> dict:
    """Build a valid ONAPPUNINSTALL payload."""
    return {
        "event": "ONAPPUNINSTALL",
        "data": {
            "LANGUAGE_ID": "ru",
            "CLEAN": 0,
        },
        "auth": {
            "domain": "test.bitrix24.ru",
            "member_id": "test-member-id",
            "application_token": "test-application-token",
            "client_endpoint": "https://test.bitrix24.ru/rest/",
            "server_endpoint": "https://oauth.bitrix24.tech/rest/",
        },
        "ts": 1730000000,
    }


def test_install_event_returns_200(client, installation_mocks):
    """A verified installation event is processed successfully."""
    service, oauth_validate, ensure_handler = installation_mocks
    portal = Mock()
    service.handle_app_install.return_value = portal

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    oauth_validate.assert_awaited_once_with(
        access_token="test-access-token",
        member_id="test-member-id",
    )
    service.handle_app_install.assert_called_once()
    ensure_handler.assert_awaited_once_with(
        client_endpoint="https://test.bitrix24.ru/rest/",
        access_token="test-access-token",
        event="ONAPPUNINSTALL",
        handler="https://example.com/events/bitrix24",
    )
    service.mark_installation_ready.assert_called_once_with(portal)


def test_install_event_validation_failure_returns_403(
    client,
    installation_mocks,
):
    """An installation event with mismatched identifiers is rejected."""
    from app.integrations.bitrix24.oauth import Bitrix24InstallationValidationError

    service, oauth_validate, ensure_handler = installation_mocks
    oauth_validate.side_effect = Bitrix24InstallationValidationError("Application ID mismatch.")

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}

    service.handle_app_install.assert_not_called()
    ensure_handler.assert_not_awaited()
    service.mark_installation_ready.assert_not_called()


def test_install_event_oauth_error_returns_403(
    client,
    installation_mocks,
):
    """An invalid access token is rejected by the authorization server."""
    from app.integrations.bitrix24.oauth import Bitrix24OAuthError

    service, oauth_validate, ensure_handler = installation_mocks
    oauth_validate.side_effect = Bitrix24OAuthError(
        "invalid_token",
        "Invalid access token",
    )

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}

    service.handle_app_install.assert_not_called()
    ensure_handler.assert_not_awaited()


def test_install_event_http_error_returns_502(
    client,
    installation_mocks,
):
    """A network failure during token validation returns 502."""
    service, oauth_validate, ensure_handler = installation_mocks
    oauth_validate.side_effect = httpx.ConnectError("Connection failed")

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 502
    assert service.handle_app_install.call_count == 0
    ensure_handler.assert_not_awaited()


def test_uninstall_event_returns_200(client, monkeypatch):
    """A valid uninstall event is processed successfully."""
    service = Mock()
    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventService",
        lambda db: service,
    )

    response = client.post(
        "/events/bitrix24",
        json=make_uninstall_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    service.handle_app_uninstall.assert_called_once()


def test_install_event_value_error_returns_400(
    client,
    installation_mocks,
):
    """Invalid installation credentials return a client error."""
    service, _, _ = installation_mocks
    service.handle_app_install.side_effect = ValueError("Invalid installation data")

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 400


def test_uninstall_invalid_token_returns_403(client, monkeypatch):
    """An uninstall event with an invalid token is rejected."""
    service = Mock()
    service.handle_app_uninstall.side_effect = InvalidApplicationToken()

    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventService",
        lambda db: service,
    )

    response = client.post(
        "/events/bitrix24",
        json=make_uninstall_payload(),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_uninstall_unknown_portal_returns_403(client, monkeypatch):
    """An uninstall event for an unknown portal is rejected."""
    service = Mock()
    service.handle_app_uninstall.side_effect = ValueError("Portal not found.")

    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventService",
        lambda db: service,
    )

    response = client.post(
        "/events/bitrix24",
        json=make_uninstall_payload(),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_invalid_event_payload_returns_422(client):
    """An unknown event type is rejected during request validation."""
    response = client.post(
        "/events/bitrix24",
        json={"event": "UNKNOWN"},
    )

    assert response.status_code == 422


def test_install_event_without_handler_url_returns_500(
    client,
    monkeypatch,
):
    """Installation is rejected when the event handler URL is missing."""

    service = Mock()
    oauth_client = Mock(validate_installation=AsyncMock())

    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventService",
        lambda db: service,
    )
    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24OAuthClient",
        lambda: oauth_client,
    )
    monkeypatch.setattr(
        "app.api.routes.events.settings.bitrix24_event_handler_url",
        "",
    )

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 500
    assert response.json()["detail"] == ("Bitrix24 event handler URL is not configured.")
    oauth_client.validate_installation.assert_not_awaited()
    service.handle_app_install.assert_not_called()


def test_install_event_bitrix_api_error_returns_502(
    client,
    installation_mocks,
):
    """A Bitrix24 REST error during uninstall-handler registration returns 502."""
    from app.integrations.bitrix24.events import Bitrix24EventAPIError

    service, _, ensure_handler = installation_mocks
    ensure_handler.side_effect = Bitrix24EventAPIError(
        "ERROR_EVENT_NOT_FOUND",
        "Event not found",
    )

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == ("Failed to register Bitrix24 event handler.")
    service.handle_app_install.assert_called_once()
    service.mark_installation_ready.assert_not_called()
