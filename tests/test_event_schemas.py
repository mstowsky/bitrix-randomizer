"""Tests for Bitrix24 event schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.events import AppInstallEvent, AppUninstallEvent


def test_app_install_event_parses_payload() -> None:
    """The ONAPPINSTALL payload is parsed correctly."""
    payload = {
        "event": "ONAPPINSTALL",
        "event_handler_id": "11",
        "ts": "1696527000",
        "data": {
            "VERSION": "1",
            "ACTIVE": "Y",
            "INSTALLED": "Y",
            "LANGUAGE_ID": "ru",
        },
        "auth": {
            "domain": "example.bitrix24.ru",
            "scope": "crm,user",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": "3600",
            "server_endpoint": "https://oauth.bitrix24.tech/rest/",
            "client_endpoint": "https://example.bitrix24.ru/rest/",
            "member_id": "member-123",
            "application_token": "application-token",
        },
    }

    event = AppInstallEvent.model_validate(payload)

    assert event.event == "ONAPPINSTALL"
    assert event.ts == 1696527000
    assert event.data.version == "1"
    assert event.data.language_id == "ru"
    assert event.auth.member_id == "member-123"
    assert event.auth.access_token == "access-token"
    assert event.auth.expires_in == 3600


def test_app_install_event_rejects_missing_application_token() -> None:
    """An install event without application_token is rejected."""
    payload = {
        "event": "ONAPPINSTALL",
        "ts": "1696527000",
        "data": {
            "VERSION": "1",
            "ACTIVE": "Y",
            "INSTALLED": "Y",
            "LANGUAGE_ID": "ru",
        },
        "auth": {
            "domain": "example.bitrix24.ru",
            "client_endpoint": "https://example.bitrix24.ru/rest/",
            "server_endpoint": "https://oauth.bitrix24.tech/rest/",
            "member_id": "member-123",
        },
    }

    with pytest.raises(ValidationError):
        AppInstallEvent.model_validate(payload)


def test_app_uninstall_event_parses_payload() -> None:
    """The ONAPPUNINSTALL payload is parsed correctly."""
    payload = {
        "event": "ONAPPUNINSTALL",
        "event_handler_id": "13",
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

    event = AppUninstallEvent.model_validate(payload)

    assert event.event == "ONAPPUNINSTALL"
    assert event.data.language_id == "ru"
    assert event.data.clean == 1
    assert event.auth.member_id == "member-123"
    assert event.auth.application_token == "application-token"
    assert event.auth.access_token is None
