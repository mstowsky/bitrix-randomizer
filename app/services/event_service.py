"""Service for processing Bitrix24 application lifecycle events."""

from datetime import UTC, datetime, timedelta
from hmac import compare_digest

from sqlalchemy.orm import Session

from app.core.security import decrypt_token
from app.database.models import Portal
from app.schemas.events import AppInstallEvent, AppUninstallEvent
from app.services.portal_service import PortalService


class InvalidApplicationToken(Exception):
    """Raised when an incoming event has an invalid application token."""


class Bitrix24EventService:
    """Process incoming Bitrix24 application events."""

    def __init__(self, db: Session) -> None:
        """Initialize the event service."""
        self.portal_service = PortalService(db)

    def handle_app_install(self, event: AppInstallEvent) -> Portal:
        """Save portal credentials received during application installation."""
        auth = event.auth

        if not auth.access_token:
            raise ValueError("Installation event has no access token.")

        if not auth.refresh_token:
            raise ValueError("Installation event has no refresh token.")

        if auth.expires_in is None or auth.expires_in <= 0:
            raise ValueError("Installation event has an invalid token lifetime.")

        expires_at = datetime.now(UTC) + timedelta(seconds=auth.expires_in)

        return self.portal_service.save_portal(
            domain=auth.domain,
            member_id=auth.member_id,
            access_token=auth.access_token,
            refresh_token=auth.refresh_token,
            access_token_expires_at=expires_at,
            client_endpoint=auth.client_endpoint,
            server_endpoint=auth.server_endpoint,
            scope=auth.scope,
            application_token=auth.application_token,
        )

    def mark_installation_ready(self, portal: Portal) -> None:
        """Mark installation as ready after all setup operations succeed."""
        self.portal_service.mark_installation_ready(portal)

    def handle_app_uninstall(self, event: AppUninstallEvent) -> Portal:
        """Verify and process application uninstallation."""
        auth = event.auth
        portal = self.portal_service.get_by_member_id(auth.member_id)

        if portal is None:
            raise ValueError("Portal not found.")

        if not portal.application_token_encrypted:
            raise InvalidApplicationToken

        stored_token = decrypt_token(portal.application_token_encrypted)

        if not compare_digest(stored_token, auth.application_token):
            raise InvalidApplicationToken

        # CLEAN is intentionally not used to delete data at this stage.
        self.portal_service.deactivate_portal(portal)

        return portal
