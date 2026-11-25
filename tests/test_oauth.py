"""Tests for the Bitrix24 OAuth client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.integrations.bitrix24.oauth import (
    OAUTH_TOKEN_URL,
    Bitrix24OAuthClient,
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


def test_oauth_client_requires_credentials() -> None:
    """The client cannot be initialized without OAuth credentials."""
    with (
        patch.object(settings, "client_id", ""),
        patch.object(settings, "client_secret", ""),
        pytest.raises(ValueError, match="credentials are not configured"),
    ):
        Bitrix24OAuthClient()


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

    async_client = MagicMock()
    async_client.__aenter__ = AsyncMock(return_value=http_client)
    async_client.__aexit__ = AsyncMock(return_value=None)

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
    response.raise_for_status.assert_called_once()


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

    async_client = MagicMock()
    async_client.__aenter__ = AsyncMock(return_value=http_client)
    async_client.__aexit__ = AsyncMock(return_value=None)

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

    async_client = MagicMock()
    async_client.__aenter__ = AsyncMock(return_value=http_client)
    async_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "app.integrations.bitrix24.oauth.httpx.AsyncClient",
            return_value=async_client,
        ),
        pytest.raises(ValueError),
    ):
        client = Bitrix24OAuthClient()
        await client.refresh_token("old-refresh-token")
