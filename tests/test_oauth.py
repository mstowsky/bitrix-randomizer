"""Tests for the Bitrix24 OAuth client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.integrations.bitrix24.oauth import (
    OAUTH_APP_INFO_URL,
    OAUTH_TOKEN_URL,
    Bitrix24InstallationValidationError,
    Bitrix24OAuthClient,
    Bitrix24OAuthError,
    OAuthTokenResponse,
)


@pytest.fixture
def oauth_credentials() -> None:
    """Configure test OAuth credentials."""
    with (
        patch.object(settings, "client_id", "test-client-id"),
        patch.object(settings, "client_secret", "test-client-secret"),
    ):
        yield


def create_async_client(http_client: AsyncMock) -> MagicMock:
    """Create a mocked asynchronous HTTP client context manager."""
    async_client = MagicMock()
    async_client.__aenter__ = AsyncMock(return_value=http_client)
    async_client.__aexit__ = AsyncMock(return_value=None)
    return async_client


def test_oauth_client_requires_credentials() -> None:
    """The client cannot be initialized without OAuth credentials."""
    with (
        patch.object(settings, "client_id", ""),
        patch.object(settings, "client_secret", ""),
        pytest.raises(ValueError, match="credentials are not configured"),
    ):
        Bitrix24OAuthClient()


@pytest.mark.anyio
async def test_validate_installation_sends_correct_request(
    oauth_credentials: None,
) -> None:
    """The installation token is checked on the fixed authorization server."""
    response = MagicMock()
    response.json.return_value = {
        "result": {
            "client_id": "test-client-id",
            "install": {"member_id": "member-123"},
        }
    }

    http_client = AsyncMock()
    http_client.post.return_value = response
    async_client = create_async_client(http_client)

    with (
        patch(
            "app.integrations.bitrix24.oauth.httpx.AsyncClient",
            return_value=async_client,
        ) as async_client_factory,
    ):
        client = Bitrix24OAuthClient()
        await client.validate_installation(
            access_token="installation-access-token",
            member_id="member-123",
        )

    async_client_factory.assert_called_once_with(timeout=15.0)
    http_client.post.assert_awaited_once_with(
        OAUTH_APP_INFO_URL,
        data={"auth": "installation-access-token"},
    )
    response.raise_for_status.assert_called_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response_data", "expected_message"),
    [
        (
            {
                "result": {
                    "client_id": "another-client-id",
                    "install": {"member_id": "member-123"},
                }
            },
            "another application",
        ),
        (
            {
                "result": {
                    "client_id": "test-client-id",
                    "install": {"member_id": "another-member"},
                }
            },
            "another Bitrix24 portal",
        ),
    ],
)
async def test_validate_installation_rejects_identifier_mismatch(
    oauth_credentials: None,
    response_data: dict[str, object],
    expected_message: str,
) -> None:
    """An event is rejected when either application or portal ID differs."""
    response = MagicMock()
    response.json.return_value = response_data

    http_client = AsyncMock()
    http_client.post.return_value = response
    async_client = create_async_client(http_client)

    with (
        patch(
            "app.integrations.bitrix24.oauth.httpx.AsyncClient",
            return_value=async_client,
        ),
        pytest.raises(
            Bitrix24InstallationValidationError,
            match=expected_message,
        ),
    ):
        client = Bitrix24OAuthClient()
        await client.validate_installation(
            access_token="installation-access-token",
            member_id="member-123",
        )


@pytest.mark.anyio
async def test_validate_installation_rejects_empty_access_token(
    oauth_credentials: None,
) -> None:
    """An empty access token is rejected without an HTTP request."""
    client = Bitrix24OAuthClient()

    with pytest.raises(ValueError, match="Access token must not be empty"):
        await client.validate_installation("", "member-123")


@pytest.mark.anyio
async def test_validate_installation_rejects_empty_member_id(
    oauth_credentials: None,
) -> None:
    """An empty member ID is rejected without an HTTP request."""
    client = Bitrix24OAuthClient()

    with pytest.raises(ValueError, match="Member ID must not be empty"):
        await client.validate_installation("access-token", "")


@pytest.mark.anyio
async def test_validate_installation_raises_structured_oauth_error(
    oauth_credentials: None,
) -> None:
    """A structured error from the authorization server is propagated safely."""
    response = MagicMock()
    response.json.return_value = {
        "error": "invalid_token",
        "error_description": "Access token is invalid",
    }

    http_client = AsyncMock()
    http_client.post.return_value = response
    async_client = create_async_client(http_client)

    with (
        patch(
            "app.integrations.bitrix24.oauth.httpx.AsyncClient",
            return_value=async_client,
        ),
        pytest.raises(Bitrix24OAuthError) as exc_info,
    ):
        client = Bitrix24OAuthClient()
        await client.validate_installation(
            access_token="installation-access-token",
            member_id="member-123",
        )

    assert exc_info.value.error == "invalid_token"
    assert "installation-access-token" not in str(exc_info.value)


@pytest.mark.anyio
async def test_validate_installation_propagates_http_error(
    oauth_credentials: None,
) -> None:
    """An HTTP error from the authorization server is propagated."""
    request = httpx.Request("POST", OAUTH_APP_INFO_URL)
    response = httpx.Response(401, request=request)
    http_error = httpx.HTTPStatusError(
        "Unauthorized",
        request=request,
        response=response,
    )

    http_client = AsyncMock()
    http_client.post.side_effect = http_error
    async_client = create_async_client(http_client)

    with (
        patch(
            "app.integrations.bitrix24.oauth.httpx.AsyncClient",
            return_value=async_client,
        ),
        pytest.raises(httpx.HTTPStatusError),
    ):
        client = Bitrix24OAuthClient()
        await client.validate_installation(
            access_token="installation-access-token",
            member_id="member-123",
        )


def test_refresh_token_rejects_empty_token(oauth_credentials: None) -> None:
    """An empty refresh token is rejected before making an HTTP request."""
    client = Bitrix24OAuthClient()

    with pytest.raises(ValueError, match="Refresh token must not be empty"):
        import asyncio

        asyncio.run(client.refresh_token(""))


@pytest.mark.anyio
async def test_refresh_token_sends_correct_request(
    oauth_credentials: None,
) -> None:
    """The OAuth client sends the expected parameters and parses the response."""
    response_data = {
        "access_token": "new-access-token",
        "refresh_token": "new-refresh-token",
        "expires_in": 3600,
        "member_id": "member-123",
        "client_endpoint": "https://example.bitrix24.ru/rest/",
        "server_endpoint": "https://oauth.bitrix24.tech/rest/",
        "scope": "crm",
        "extra_field": "ignored",
    }

    response = MagicMock()
    response.json.return_value = response_data
    response.raise_for_status.return_value = None

    http_client = AsyncMock()
    http_client.get.return_value = response
    async_client = create_async_client(http_client)

    with patch(
        "app.integrations.bitrix24.oauth.httpx.AsyncClient",
        return_value=async_client,
    ) as async_client_factory:
        client = Bitrix24OAuthClient()
        result = await client.refresh_token("old-refresh-token")

    assert isinstance(result, OAuthTokenResponse)
    assert result.access_token == "new-access-token"
    assert result.refresh_token == "new-refresh-token"
    assert result.expires_in == 3600
    assert result.member_id == "member-123"
    assert result.scope == "crm"

    async_client_factory.assert_called_once_with(timeout=15.0)
    http_client.get.assert_awaited_once_with(
        OAUTH_TOKEN_URL,
        params={
            "grant_type": "refresh_token",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "refresh_token": "old-refresh-token",
        },
    )
    assert response.raise_for_status.call_count == 0


@pytest.mark.anyio
async def test_refresh_token_propagates_http_error(
    oauth_credentials: None,
) -> None:
    """An HTTP error from the OAuth server is propagated."""
    request = httpx.Request("GET", OAUTH_TOKEN_URL)
    response = httpx.Response(401, request=request)
    http_error = httpx.HTTPStatusError(
        "Unauthorized",
        request=request,
        response=response,
    )

    http_client = AsyncMock()
    http_client.get.side_effect = http_error
    async_client = create_async_client(http_client)

    with (
        patch(
            "app.integrations.bitrix24.oauth.httpx.AsyncClient",
            return_value=async_client,
        ),
        pytest.raises(httpx.HTTPStatusError),
    ):
        client = Bitrix24OAuthClient()
        await client.refresh_token("old-refresh-token")


@pytest.mark.anyio
async def test_refresh_token_rejects_invalid_response(
    oauth_credentials: None,
) -> None:
    """An invalid OAuth response is rejected during model validation."""
    response = MagicMock()
    response.json.return_value = {"access_token": "incomplete"}
    response.raise_for_status.return_value = None

    http_client = AsyncMock()
    http_client.get.return_value = response
    async_client = create_async_client(http_client)

    with (
        patch(
            "app.integrations.bitrix24.oauth.httpx.AsyncClient",
            return_value=async_client,
        ),
        pytest.raises(ValueError),
    ):
        client = Bitrix24OAuthClient()
        await client.refresh_token("old-refresh-token")


@pytest.mark.anyio
async def test_refresh_token_raises_structured_oauth_error(
    oauth_credentials: None,
) -> None:
    """A structured error from the OAuth server is exposed safely."""
    response = MagicMock()
    response.is_success = False
    response.json.return_value = {
        "error": "invalid_grant",
        "error_description": "Refresh token expired",
    }

    http_client = AsyncMock()
    http_client.get.return_value = response
    async_client = create_async_client(http_client)

    with (
        patch(
            "app.integrations.bitrix24.oauth.httpx.AsyncClient",
            return_value=async_client,
        ),
        pytest.raises(Bitrix24OAuthError) as exc_info,
    ):
        client = Bitrix24OAuthClient()
        await client.refresh_token("old-refresh-token")

    assert exc_info.value.error == "invalid_grant"
    assert exc_info.value.description == "Refresh token expired"
    assert "old-refresh-token" not in str(exc_info.value)


@pytest.mark.anyio
async def test_refresh_token_raises_structured_oauth_error_on_success_status(
    oauth_credentials: None,
) -> None:
    """A structured OAuth error is recognized even with a success HTTP status."""
    response = MagicMock()
    response.is_success = True
    response.json.return_value = {
        "error": "invalid_grant",
        "error_description": "Refresh token expired",
    }

    http_client = AsyncMock()
    http_client.get.return_value = response
    async_client = create_async_client(http_client)

    with (
        patch(
            "app.integrations.bitrix24.oauth.httpx.AsyncClient",
            return_value=async_client,
        ),
        pytest.raises(Bitrix24OAuthError) as exc_info,
    ):
        client = Bitrix24OAuthClient()
        await client.refresh_token("old-refresh-token")

    assert exc_info.value.error == "invalid_grant"
    assert exc_info.value.description == "Refresh token expired"
