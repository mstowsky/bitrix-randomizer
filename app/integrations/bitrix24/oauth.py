"""OAuth client for Bitrix24 token operations."""

import httpx
from pydantic import BaseModel, ConfigDict

from app.core.config import settings

OAUTH_TOKEN_URL = "https://oauth.bitrix24.tech/oauth/token/"
OAUTH_APP_INFO_URL = "https://oauth.bitrix24.tech/rest/app.info"


class Bitrix24OAuthError(Exception):
    """Error returned by the Bitrix24 OAuth authorization server."""

    def __init__(self, error: str, description: str) -> None:
        self.error = error
        self.description = description
        super().__init__(f"Bitrix24 OAuth error: {error}")


class Bitrix24InstallationValidationError(Exception):
    """Raised when an installation event cannot be verified."""


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


class OAuthAppInfoInstall(BaseModel):
    """Installation information returned by the authorization server."""

    model_config = ConfigDict(extra="ignore")

    member_id: str


class OAuthAppInfoResult(BaseModel):
    """Application information returned by the authorization server."""

    model_config = ConfigDict(extra="ignore")

    client_id: str
    install: OAuthAppInfoInstall


class OAuthAppInfoResponse(BaseModel):
    """Response returned by the authorization server app.info endpoint."""

    model_config = ConfigDict(extra="ignore")

    result: OAuthAppInfoResult


class Bitrix24OAuthClient:
    """Client for communicating with the Bitrix24 OAuth server."""

    def __init__(self) -> None:
        """Initialize the OAuth client."""
        if not settings.client_id or not settings.client_secret:
            raise ValueError("Bitrix24 OAuth client credentials are not configured.")

        self.client_id = settings.client_id
        self.client_secret = settings.client_secret

    async def validate_installation(
        self,
        access_token: str,
        member_id: str,
    ) -> None:
        """Verify an installation token against the Bitrix24 authorization server."""
        if not access_token:
            raise ValueError("Access token must not be empty.")

        if not member_id:
            raise ValueError("Member ID must not be empty.")

        # Use the fixed authorization server URL, not an address from the event.
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                OAUTH_APP_INFO_URL,
                data={"auth": access_token},
            )
            response.raise_for_status()

            response_data = response.json()

        # Handle structured errors returned with a successful HTTP status.
        if isinstance(response_data, dict) and response_data.get("error"):
            raise Bitrix24OAuthError(
                error=str(response_data["error"]),
                description=str(response_data.get("error_description", "")),
            )

        app_info = OAuthAppInfoResponse.model_validate(response_data)

        # Both identifiers must match before installation credentials are trusted.
        if app_info.result.client_id != self.client_id:
            raise Bitrix24InstallationValidationError(
                "The installation event belongs to another application."
            )

        if app_info.result.install.member_id != member_id:
            raise Bitrix24InstallationValidationError(
                "The installation event belongs to another Bitrix24 portal."
            )

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

            try:
                response_data = response.json()
            except ValueError:
                if not response.is_success:
                    response.raise_for_status()
                raise

            if isinstance(response_data, dict) and response_data.get("error"):
                raise Bitrix24OAuthError(
                    error=str(response_data["error"]),
                    description=str(response_data.get("error_description", "")),
                )

            if not response.is_success:
                response.raise_for_status()

            return OAuthTokenResponse.model_validate(response_data)
