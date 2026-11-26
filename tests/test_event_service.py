"""Tests for Bitrix24 application event service."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.core.security import encrypt_token
from app.schemas.events import AppInstallEvent, AppUninstallEvent
from app.services.event_service import Bitrix24EventService, InvalidApplicationToken


@pytest.fixture
def install_event() -> AppInstallEvent:
    """Provide a valid ONAPPINSTALL event."""
    return AppInstallEvent.model_validate(
        {
            "event": "ONAPPINSTALL",
            "ts": "1696527000",
            "data": {
                "VERSION": "1",
                "LANGUAGE_ID": "ru",
            },
            "auth": {
                "domain": "example.bitrix24.ru",
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": "3600",
                "scope": "crm,user",
                "server_endpoint": "https://oauth.bitrix24.tech/rest/",
                "client_endpoint": "https://example.bitrix24.ru/rest/",
                "member_id": "member-123",
                "application_token": "application-token",
            },
        }
    )


@pytest.fixture
def uninstall_event() -> AppUninstallEvent:
    """Provide a valid ONAPPUNINSTALL event."""
    return AppUninstallEvent.model_validate(
        {
            "event": "ONAPPUNINSTALL",
            "ts": "1696527000",
            "data": {
                "LANGUAGE_ID": "ru",
                "CLEAN": "1",
            },
            "auth": {
                "domain": "example.bitrix24.ru",
                "server_endpoint": "https://oauth.bitrix24.tech/rest/",
                "client_endpoint": "https://example.bitrix24.ru/rest/",
                "member_id": "member-123",
                "application_token": "application-token",
            },
        }
    )


@pytest.fixture
def event_service() -> Bitrix24EventService:
    """Provide an event service with a mocked portal service."""
    with patch("app.services.event_service.PortalService") as portal_service_class:
        service = Bitrix24EventService(MagicMock())
        service.portal_service = portal_service_class.return_value

    return service


def test_handle_app_install_saves_portal(
    event_service: Bitrix24EventService,
    install_event: AppInstallEvent,
) -> None:
    """Installation credentials are forwarded to the portal service."""
    expected_portal = MagicMock()
    event_service.portal_service.save_portal.return_value = expected_portal

    result = event_service.handle_app_install(install_event)

    assert result is expected_portal

    event_service.portal_service.save_portal.assert_called_once()
    saved_values = event_service.portal_service.save_portal.call_args.kwargs

    assert saved_values["domain"] == "example.bitrix24.ru"
    assert saved_values["member_id"] == "member-123"
    assert saved_values["access_token"] == "access-token"
    assert saved_values["refresh_token"] == "refresh-token"
    assert saved_values["application_token"] == "application-token"
    assert saved_values["scope"] == "crm,user"
    assert saved_values["access_token_expires_at"].tzinfo == UTC

    remaining = (saved_values["access_token_expires_at"] - datetime.now(UTC)).total_seconds()
    assert 3590 < remaining <= 3600


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("access_token", None, "no access token"),
        ("refresh_token", None, "no refresh token"),
        ("expires_in", 0, "invalid token lifetime"),
        ("expires_in", -1, "invalid token lifetime"),
    ],
)
def test_handle_app_install_rejects_invalid_credentials(
    event_service: Bitrix24EventService,
    install_event: AppInstallEvent,
    field: str,
    value: str | int | None,
    error: str,
) -> None:
    """Invalid installation credentials are rejected."""
    setattr(install_event.auth, field, value)

    with pytest.raises(ValueError, match=error):
        event_service.handle_app_install(install_event)

    event_service.portal_service.save_portal.assert_not_called()


@pytest.mark.parametrize("clean", [0, 1])
def test_handle_app_uninstall_deactivates_portal(
    event_service: Bitrix24EventService,
    uninstall_event: AppUninstallEvent,
    clean: int,
) -> None:
    """A valid uninstall event deactivates the portal without deleting data."""
    uninstall_event.data.clean = clean

    portal = MagicMock()
    portal.application_token_encrypted = encrypt_token("application-token")
    event_service.portal_service.get_by_member_id.return_value = portal

    result = event_service.handle_app_uninstall(uninstall_event)

    assert result is portal
    event_service.portal_service.get_by_member_id.assert_called_once_with("member-123")
    event_service.portal_service.deactivate_portal.assert_called_once_with(portal)
    event_service.portal_service.delete.assert_not_called()


def test_handle_app_uninstall_rejects_invalid_token(
    event_service: Bitrix24EventService,
    uninstall_event: AppUninstallEvent,
) -> None:
    """An uninstall event with an invalid application token is rejected."""
    portal = MagicMock()
    portal.application_token_encrypted = encrypt_token("stored-token")
    event_service.portal_service.get_by_member_id.return_value = portal

    with pytest.raises(InvalidApplicationToken):
        event_service.handle_app_uninstall(uninstall_event)

    event_service.portal_service.deactivate_portal.assert_not_called()


def test_handle_app_uninstall_rejects_unknown_portal(
    event_service: Bitrix24EventService,
    uninstall_event: AppUninstallEvent,
) -> None:
    """An uninstall event for an unknown portal is rejected."""
    event_service.portal_service.get_by_member_id.return_value = None

    with pytest.raises(ValueError, match="Portal not found"):
        event_service.handle_app_uninstall(uninstall_event)

    event_service.portal_service.deactivate_portal.assert_not_called()


def test_handle_app_uninstall_rejects_missing_stored_token(
    event_service: Bitrix24EventService,
    uninstall_event: AppUninstallEvent,
) -> None:
    """An uninstall event is rejected when no token is stored."""
    portal = MagicMock()
    portal.application_token_encrypted = None
    event_service.portal_service.get_by_member_id.return_value = portal

    with pytest.raises(InvalidApplicationToken):
        event_service.handle_app_uninstall(uninstall_event)

    event_service.portal_service.deactivate_portal.assert_not_called()
