"""Tests for Bitrix24 application event endpoints."""

from unittest.mock import AsyncMock

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


def make_install_payload() -> dict:
    return {
        "event": "ONAPPINSTALL",
        "data": {
            "VERSION": "1",
            "ACTIVE": "Y",
            "INSTALLED": "Y",
            "LANGUAGE_ID": "ru",
        },
        "auth": {
            "domain": "test.bitrix24.ru",
            "member_id": "test-member-id",
            "application_token": "test-application-token",
            "client_endpoint": "https://test.bitrix24.ru/rest/",
            "server_endpoint": "https://oauth.bitrix.info/rest/",
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600,
            "scope": "crm",
        },
        "ts": 1730000000,
    }


def make_uninstall_payload() -> dict:
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
            "server_endpoint": "https://oauth.bitrix.info/rest/",
        },
        "ts": 1730000000,
    }


def test_install_event_returns_200(client, monkeypatch):
    from unittest.mock import Mock

    service = Mock()
    ensure_handler = AsyncMock(return_value=True)

    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventService",
        lambda db: service,
    )
    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventClient.ensure_event_handler",
        ensure_handler,
    )
    monkeypatch.setattr(
        "app.api.routes.events.settings.bitrix24_event_handler_url",
        "https://example.com/events/bitrix24",
    )

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    service.handle_app_install.assert_called_once()
    ensure_handler.assert_awaited_once_with(
        client_endpoint="https://test.bitrix24.ru/rest/",
        access_token="test-access-token",
        event="ONAPPUNINSTALL",
        handler="https://example.com/events/bitrix24",
    )


def test_uninstall_event_returns_200(client, monkeypatch):
    from unittest.mock import Mock

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


def test_install_event_value_error_returns_400(client, monkeypatch):
    from unittest.mock import Mock

    service = Mock()
    service.handle_app_install.side_effect = ValueError("Invalid installation data")

    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventService",
        lambda db: service,
    )

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 400


def test_uninstall_invalid_token_returns_403(client, monkeypatch):
    from unittest.mock import Mock

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
    from unittest.mock import Mock

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
    response = client.post(
        "/events/bitrix24",
        json={"event": "UNKNOWN"},
    )

    assert response.status_code == 422


def test_install_event_without_handler_url_returns_500(client, monkeypatch):
    from unittest.mock import Mock

    service = Mock()

    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventService",
        lambda db: service,
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


def test_install_event_bitrix_api_error_returns_502(client, monkeypatch):
    from unittest.mock import Mock

    from app.integrations.bitrix24.events import Bitrix24EventAPIError

    service = Mock()
    ensure_handler = AsyncMock(
        side_effect=Bitrix24EventAPIError(
            "ERROR_EVENT_NOT_FOUND",
            "Event not found",
        )
    )

    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventService",
        lambda db: service,
    )
    monkeypatch.setattr(
        "app.api.routes.events.Bitrix24EventClient.ensure_event_handler",
        ensure_handler,
    )
    monkeypatch.setattr(
        "app.api.routes.events.settings.bitrix24_event_handler_url",
        "https://example.com/events/bitrix24",
    )

    response = client.post(
        "/events/bitrix24",
        json=make_install_payload(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == ("Failed to register Bitrix24 event handler.")
