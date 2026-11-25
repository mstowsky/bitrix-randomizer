"""OAuth client for Bitrix24 token operations."""

import httpx
from pydantic import BaseModel, ConfigDict

from app.core.config import settings

OAUTH_TOKEN_URL = "https://oauth.bitrix24.tech/oauth/token/"


class Bitrix24OAuthError(Exception):
    """Error returned by the Bitrix24 OAuth authorization server."""

    def __init__(self, error: str, description: str) -> None:
        self.error = error
        self.description = description
        super().__init__(f"Bitrix24 OAuth error: {error}")


class OAuthTokenResponse(BaseModel):
    """Token response returned by the Bitrix24 OAuth server."""

    model_config = ConfigDict(extra="ignore")

    access_token: str
    refresh_token: str
    expires_in: int
    member_id: str
    client_endpoint: str
    server_endpoint: str
    domain: str | None = None
    scope: str | None = None
    status: str | None = None


class Bitrix24OAuthClient:
    """Client for communicating with the Bitrix24 OAuth server."""

    def __init__(self) -> None:
        """Initialize the OAuth client."""
        if not settings.client_id or not settings.client_secret:
            raise ValueError("Bitrix24 OAuth client credentials are not configured.")

        self.client_id = settings.client_id
        self.client_secret = settings.client_secret

    async def refresh_token(self, refresh_token: str) -> OAuthTokenResponse:
        """Exchange a refresh token for a new pair of OAuth tokens."""
        if not refresh_token:
            raise ValueError("Refresh token must not be empty.")

        params = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(OAUTH_TOKEN_URL, params=params)

            if not response.is_success:
                try:
                    error_data = response.json()
                except ValueError:
                    error_data = {}

                if isinstance(error_data, dict) and error_data.get("error"):
                    raise Bitrix24OAuthError(
                        error=str(error_data["error"]),
                        description=str(error_data.get("error_description", "")),
                    )

                response.raise_for_status()

            return OAuthTokenResponse.model_validate(response.json())
