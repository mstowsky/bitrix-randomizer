"""Service for processing Bitrix24 application lifecycle events."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.database.models import Portal
from app.schemas.events import AppInstallEvent
from app.services.portal_service import PortalService


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
