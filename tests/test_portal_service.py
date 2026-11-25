"""Tests for the portal service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.database.models import Portal
from app.integrations.bitrix24.oauth import Bitrix24OAuthError, OAuthTokenResponse
from app.services.portal_service import PortalReauthorizationRequired, PortalService


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio as the backend for async tests."""
    return "asyncio"


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
    repository.update.assert_called_once()

    updated_portal = repository.update.call_args.args[0]
    updated_values = repository.update.call_args.kwargs

    assert updated_portal is portal
    assert updated_values["access_token_encrypted"] == "encrypted:new-access"
    assert updated_values["refresh_token_encrypted"] == "encrypted:new-refresh"

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


@pytest.mark.anyio
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
    oauth_client.refresh_token = AsyncMock(return_value=token_data)

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


@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
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
    oauth_client.refresh_token = AsyncMock(return_value=token_data)

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


@pytest.mark.anyio
async def test_get_valid_access_token_returns_existing_token(
    service: PortalService,
    repository: MagicMock,
) -> None:
    """A valid access token is returned without refreshing it."""
    portal_id = uuid4()
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
        access_token_encrypted="encrypted:access-123",
        access_token_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    repository.get_by_id.return_value = portal

    with (
        patch(
            "app.services.portal_service.decrypt_token",
            return_value="access-123",
        ) as decrypt,
        patch.object(
            service,
            "refresh_portal_tokens",
            new_callable=AsyncMock,
        ) as refresh,
    ):
        result = await service.get_valid_access_token(portal_id)

    assert result == "access-123"
    decrypt.assert_called_once_with("encrypted:access-123")
    refresh.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "expires_at",
    [
        datetime.now(UTC) - timedelta(minutes=1),
        datetime.now(UTC) + timedelta(seconds=30),
    ],
)
async def test_get_valid_access_token_refreshes_expiring_token(
    service: PortalService,
    repository: MagicMock,
    expires_at: datetime,
) -> None:
    """An expired or nearly expired token is refreshed."""
    portal_id = uuid4()
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
        access_token_encrypted="encrypted:old-access",
        access_token_expires_at=expires_at,
    )
    repository.get_by_id.return_value = portal

    with (
        patch(
            "app.services.portal_service.decrypt_token",
            return_value="new-access",
        ) as decrypt,
        patch.object(
            service,
            "refresh_portal_tokens",
            new_callable=AsyncMock,
            return_value=portal,
        ) as refresh,
    ):
        result = await service.get_valid_access_token(portal_id)

    assert result == "new-access"
    refresh.assert_awaited_once_with(portal_id)
    decrypt.assert_called_once_with("encrypted:old-access")


@pytest.mark.anyio
async def test_get_valid_access_token_refreshes_when_expiration_is_unknown(
    service: PortalService,
    repository: MagicMock,
) -> None:
    """A token without a known expiration is refreshed."""
    portal_id = uuid4()
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
        access_token_encrypted="encrypted:old-access",
        access_token_expires_at=None,
    )
    repository.get_by_id.return_value = portal

    with (
        patch(
            "app.services.portal_service.decrypt_token",
            return_value="new-access",
        ) as decrypt,
        patch.object(
            service,
            "refresh_portal_tokens",
            new_callable=AsyncMock,
            return_value=portal,
        ) as refresh,
    ):
        result = await service.get_valid_access_token(portal_id)

    assert result == "new-access"
    refresh.assert_awaited_once_with(portal_id)
    decrypt.assert_called_once_with("encrypted:old-access")


@pytest.mark.anyio
async def test_get_valid_access_token_rejects_unknown_portal(
    service: PortalService,
    repository: MagicMock,
) -> None:
    """An unknown portal cannot provide an access token."""
    repository.get_by_id.return_value = None

    with pytest.raises(ValueError, match="Portal not found"):
        await service.get_valid_access_token(uuid4())


@pytest.mark.anyio
async def test_get_valid_access_token_rejects_missing_access_token(
    service: PortalService,
    repository: MagicMock,
) -> None:
    """A portal without a stored access token is rejected."""
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
        access_token_encrypted=None,
    )
    repository.get_by_id.return_value = portal

    with pytest.raises(ValueError, match="no stored access token"):
        await service.get_valid_access_token(uuid4())


@pytest.mark.anyio
async def test_refresh_portal_tokens_requires_reauthorization(
    service: PortalService,
    db: MagicMock,
    repository: MagicMock,
) -> None:
    """An invalid refresh token requires portal reauthorization."""
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
        refresh_token_encrypted="encrypted:old-refresh",
    )
    repository.get_by_id.return_value = portal

    oauth_client = MagicMock()
    oauth_client.refresh_token = AsyncMock(
        side_effect=Bitrix24OAuthError(
            error="invalid_grant",
            description="Refresh token expired",
        )
    )

    with (
        patch(
            "app.services.portal_service.decrypt_token",
            return_value="old-refresh",
        ),
        patch(
            "app.services.portal_service.Bitrix24OAuthClient",
            return_value=oauth_client,
        ),
        pytest.raises(PortalReauthorizationRequired),
    ):
        await service.refresh_portal_tokens(uuid4())

    oauth_client.refresh_token.assert_awaited_once_with("old-refresh")
    repository.update.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


@pytest.mark.anyio
async def test_refresh_portal_tokens_propagates_other_oauth_errors(
    service: PortalService,
    repository: MagicMock,
) -> None:
    """OAuth errors other than invalid_grant are propagated unchanged."""
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
        refresh_token_encrypted="encrypted:old-refresh",
    )
    repository.get_by_id.return_value = portal

    oauth_error = Bitrix24OAuthError(
        error="invalid_client",
        description="Client authentication failed",
    )

    oauth_client = MagicMock()
    oauth_client.refresh_token = AsyncMock(side_effect=oauth_error)

    with (
        patch(
            "app.services.portal_service.decrypt_token",
            return_value="old-refresh",
        ),
        patch(
            "app.services.portal_service.Bitrix24OAuthClient",
            return_value=oauth_client,
        ),
        pytest.raises(Bitrix24OAuthError) as exc_info,
    ):
        await service.refresh_portal_tokens(uuid4())

    assert exc_info.value is oauth_error
    assert exc_info.value.error == "invalid_client"
    repository.update.assert_not_called()


@pytest.mark.anyio
async def test_get_valid_access_token_requires_reauthorization(
    service: PortalService,
    repository: MagicMock,
) -> None:
    """An invalid refresh token requires portal reauthorization."""
    portal_id = uuid4()
    portal = Portal(
        domain="example.bitrix24.ru",
        member_id="member-123",
        access_token_encrypted="encrypted:old-access",
        access_token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    repository.get_by_id.return_value = portal

    with (
        patch.object(
            service,
            "refresh_portal_tokens",
            new_callable=AsyncMock,
            side_effect=PortalReauthorizationRequired,
        ) as refresh,
        pytest.raises(PortalReauthorizationRequired),
    ):
        await service.get_valid_access_token(portal_id)

    refresh.assert_awaited_once_with(portal_id)
