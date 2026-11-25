"""Tests for the portal service."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.database.models import Portal
from app.integrations.bitrix24.oauth import OAuthTokenResponse
from app.services.portal_service import PortalService


@pytest.fixture
def db() -> MagicMock:
    """Provide a mocked database session."""
    return MagicMock()


@pytest.fixture
def repository() -> MagicMock:
    """Provide a mocked portal repository."""
    return MagicMock()


@pytest.fixture
def service(db: MagicMock, repository: MagicMock) -> PortalService:
    """Provide a portal service with a mocked repository."""
    with patch(
        "app.services.portal_service.PortalRepository",
        return_value=repository,
    ):
        result = PortalService(db)

    return result


def test_save_portal_creates_new_portal(
    service: PortalService,
    db: MagicMock,
    repository: MagicMock,
) -> None:
    """A new portal is created with encrypted OAuth tokens."""
    repository.get_by_member_id.return_value = None
    repository.get_by_domain.return_value = None

    with patch(
        "app.services.portal_service.encrypt_token",
        side_effect=lambda token: f"encrypted:{token}",
    ):
        portal = service.save_portal(
            domain="example.bitrix24.ru",
            member_id="member-123",
            access_token="access-123",
            refresh_token="refresh-123",
            access_token_expires_at=datetime.now(UTC),
            application_token="application-123",
        )

    assert isinstance(portal, Portal)
    assert portal.domain == "example.bitrix24.ru"
    assert portal.member_id == "member-123"
    assert portal.access_token_encrypted == "encrypted:access-123"
    assert portal.refresh_token_encrypted == "encrypted:refresh-123"
    assert portal.application_token_encrypted == "encrypted:application-123"

    repository.create.assert_called_once_with(portal)
    db.commit.assert_called_once()


def test_save_portal_updates_existing_portal(
    service: PortalService,
    db: MagicMock,
    repository: MagicMock,
) -> None:
    """An existing portal is updated instead of duplicated."""
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
    )
    repository.get_by_member_id.return_value = portal
    repository.get_by_domain.return_value = portal

    with patch(
        "app.services.portal_service.encrypt_token",
        side_effect=lambda token: f"encrypted:{token}",
    ):
        result = service.save_portal(
            domain="example.bitrix24.ru",
            member_id="member-123",
            access_token="new-access",
            refresh_token="new-refresh",
            access_token_expires_at=datetime.now(UTC),
        )

    assert result is portal
    assert portal.access_token_encrypted == "encrypted:new-access"
    assert portal.refresh_token_encrypted == "encrypted:new-refresh"

    repository.update.assert_called_once()
    repository.create.assert_not_called()
    db.commit.assert_called_once()


def test_save_portal_rejects_domain_owned_by_another_portal(
    service: PortalService,
    db: MagicMock,
    repository: MagicMock,
) -> None:
    """A domain already assigned to another portal cannot be reused."""
    existing_portal = Portal(
        domain="example.bitrix24.ru",
        member_id="another-member",
    )
    repository.get_by_member_id.return_value = None
    repository.get_by_domain.return_value = existing_portal

    with pytest.raises(ValueError, match="already registered"):
        service.save_portal(
            domain="example.bitrix24.ru",
            member_id="member-123",
            access_token="access-123",
            refresh_token="refresh-123",
            access_token_expires_at=datetime.now(UTC),
        )

    repository.create.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_portal_tokens_saves_new_tokens(
    service: PortalService,
    db: MagicMock,
    repository: MagicMock,
) -> None:
    """Refreshing tokens stores the new encrypted token pair."""
    portal_id = uuid4()
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
        refresh_token_encrypted="encrypted:old-refresh",
    )
    repository.get_by_id.return_value = portal

    token_data = OAuthTokenResponse(
        access_token="new-access",
        refresh_token="new-refresh",
        expires_in=3600,
        member_id="member-123",
        client_endpoint="https://example.bitrix24.ru/rest/",
        server_endpoint="https://oauth.bitrix24.tech/rest/",
        scope="crm",
    )

    oauth_client = MagicMock()
    oauth_client.refresh_token.return_value = token_data

    with (
        patch(
            "app.services.portal_service.decrypt_token",
            return_value="old-refresh",
        ) as decrypt,
        patch(
            "app.services.portal_service.encrypt_token",
            side_effect=lambda token: f"encrypted:{token}",
        ),
        patch(
            "app.services.portal_service.Bitrix24OAuthClient",
            return_value=oauth_client,
        ),
    ):
        result = await service.refresh_portal_tokens(portal_id)

    assert result is portal
    decrypt.assert_called_once_with("encrypted:old-refresh")
    oauth_client.refresh_token.assert_awaited_once_with("old-refresh")

    repository.get_by_id.assert_called_once_with(portal_id)
    repository.update.assert_called_once()

    updated_values = repository.update.call_args.kwargs
    assert updated_values["access_token_encrypted"] == "encrypted:new-access"
    assert updated_values["refresh_token_encrypted"] == "encrypted:new-refresh"
    assert updated_values["client_endpoint"] == token_data.client_endpoint
    assert updated_values["server_endpoint"] == token_data.server_endpoint
    assert updated_values["scope"] == "crm"

    expires_at = updated_values["access_token_expires_at"]
    assert expires_at.tzinfo is not None

    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_portal_tokens_rejects_unknown_portal(
    service: PortalService,
    db: MagicMock,
    repository: MagicMock,
) -> None:
    """Refreshing tokens for an unknown portal raises an error."""
    repository.get_by_id.return_value = None

    with pytest.raises(ValueError, match="Portal not found"):
        await service.refresh_portal_tokens(uuid4())

    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_portal_tokens_rejects_missing_refresh_token(
    service: PortalService,
    db: MagicMock,
    repository: MagicMock,
) -> None:
    """Refreshing tokens without a stored refresh token is rejected."""
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
    )
    repository.get_by_id.return_value = portal

    with pytest.raises(ValueError, match="no stored refresh token"):
        await service.refresh_portal_tokens(uuid4())

    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_portal_tokens_rejects_different_member_id(
    service: PortalService,
    db: MagicMock,
    repository: MagicMock,
) -> None:
    """Tokens belonging to another portal are not persisted."""
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
        refresh_token_encrypted="encrypted:old-refresh",
    )
    repository.get_by_id.return_value = portal

    token_data = OAuthTokenResponse(
        access_token="new-access",
        refresh_token="new-refresh",
        expires_in=3600,
        member_id="another-member",
        client_endpoint="https://example.bitrix24.ru/rest/",
        server_endpoint="https://oauth.bitrix24.tech/rest/",
    )

    oauth_client = MagicMock()
    oauth_client.refresh_token.return_value = token_data

    with (
        patch(
            "app.services.portal_service.decrypt_token",
            return_value="old-refresh",
        ),
        patch(
            "app.services.portal_service.Bitrix24OAuthClient",
            return_value=oauth_client,
        ),
        pytest.raises(ValueError, match="another portal"),
    ):
        await service.refresh_portal_tokens(uuid4())

    repository.update.assert_not_called()
    db.commit.assert_not_called()
