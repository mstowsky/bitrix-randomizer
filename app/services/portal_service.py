"""Service for managing connected Bitrix24 portals."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import decrypt_token, encrypt_token
from app.database.models import Portal
from app.database.repositories.portal_repository import PortalRepository
from app.integrations.bitrix24.oauth import Bitrix24OAuthClient


class PortalService:
    """Manage portal registration and OAuth credentials."""

    def __init__(self, db: Session) -> None:
        """Initialize the service with a database session."""
        self.db = db
        self.repository = PortalRepository(db)

    def save_portal(
        self,
        *,
        domain: str,
        member_id: str,
        access_token: str,
        refresh_token: str,
        access_token_expires_at: datetime,
        client_endpoint: str | None = None,
        server_endpoint: str | None = None,
        scope: str | None = None,
        application_token: str | None = None,
    ) -> Portal:
        """Create or update a portal and its encrypted OAuth credentials."""
        portal = self.repository.get_by_member_id(member_id)

        # Prevent another portal from already using the requested domain.
        domain_owner = self.repository.get_by_domain(domain)
        if domain_owner is not None and (portal is None or domain_owner.id != portal.id):
            raise ValueError("This domain is already registered to another portal.")

        # Encrypt sensitive credentials before writing them to the database.
        encrypted_values = {
            "domain": domain,
            "member_id": member_id,
            "access_token_encrypted": encrypt_token(access_token),
            "refresh_token_encrypted": encrypt_token(refresh_token),
            "access_token_expires_at": access_token_expires_at,
            "client_endpoint": client_endpoint,
            "server_endpoint": server_endpoint,
            "scope": scope,
            "application_token_encrypted": (
                encrypt_token(application_token) if application_token else None
            ),
        }

        try:
            if portal is None:
                portal = Portal(**encrypted_values)
                self.repository.create(portal)
            else:
                self.repository.update(portal, **encrypted_values)

            self.db.commit()
            return portal
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, portal_id: UUID) -> Portal | None:
        """Get a portal by its internal identifier."""
        return self.repository.get_by_id(portal_id)

    def get_by_member_id(self, member_id: str) -> Portal | None:
        """Get a portal by its Bitrix24 member identifier."""
        return self.repository.get_by_member_id(member_id)

    async def refresh_portal_tokens(self, portal_id: UUID) -> Portal:
        """Refresh and persist OAuth tokens for a connected portal."""
        portal = self.repository.get_by_id(portal_id)

        if portal is None:
            raise ValueError("Portal not found.")

        if not portal.refresh_token_encrypted:
            raise ValueError("Portal has no stored refresh token.")

        # Decrypt the current refresh token before sending it to Bitrix24.
        refresh_token = decrypt_token(portal.refresh_token_encrypted)

        oauth_client = Bitrix24OAuthClient()
        token_data = await oauth_client.refresh_token(refresh_token)

        # Ensure that the refreshed credentials belong to the requested portal.
        if token_data.member_id != portal.member_id:
            raise ValueError("OAuth response belongs to another portal.")

        # Calculate the expiration time using the lifetime returned by Bitrix24.
        expires_at = datetime.now(UTC) + timedelta(seconds=token_data.expires_in)

        try:
            self.repository.update(
                portal,
                access_token_encrypted=encrypt_token(token_data.access_token),
                refresh_token_encrypted=encrypt_token(token_data.refresh_token),
                access_token_expires_at=expires_at,
                client_endpoint=token_data.client_endpoint,
                server_endpoint=token_data.server_endpoint,
                scope=token_data.scope,
            )
            self.db.commit()
            return portal
        except Exception:
            self.db.rollback()
            raise
