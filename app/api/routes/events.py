"""Bitrix24 application event endpoints."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.integrations.bitrix24.events import (
    Bitrix24EventAPIError,
    Bitrix24EventClient,
)
from app.integrations.bitrix24.oauth import (
    Bitrix24InstallationValidationError,
    Bitrix24OAuthClient,
    Bitrix24OAuthError,
)
from app.schemas.events import AppInstallEvent, AppUninstallEvent
from app.services.event_service import (
    Bitrix24EventService,
    InvalidApplicationToken,
)

router = APIRouter()
DB_DEPENDENCY = Depends(get_db)

Bitrix24Event = Annotated[
    AppInstallEvent | AppUninstallEvent,
    Body(discriminator="event"),
]


@router.post("/events/bitrix24", tags=["events"])
async def handle_bitrix24_event(
    event: Bitrix24Event,
    db: Session = DB_DEPENDENCY,
) -> dict[str, str]:
    """Process incoming Bitrix24 application lifecycle events."""
    service = Bitrix24EventService(db)

    try:
        if isinstance(event, AppInstallEvent):
            # Check required configuration before accepting installation credentials.
            if not settings.bitrix24_event_handler_url:
                raise HTTPException(
                    status_code=500,
                    detail="Bitrix24 event handler URL is not configured.",
                )

            # Verify the event against the fixed Bitrix24 authorization server.
            oauth_client = Bitrix24OAuthClient()
            await oauth_client.validate_installation(
                access_token=event.auth.access_token or "",
                member_id=event.auth.member_id,
            )

            # Store credentials only after the installation event is verified.
            portal = service.handle_app_install(event)

            # Register the uninstall handler after the portal credentials are saved.
            event_client = Bitrix24EventClient()
            await event_client.ensure_event_handler(
                client_endpoint=event.auth.client_endpoint,
                access_token=event.auth.access_token,
                event="ONAPPUNINSTALL",
                handler=settings.bitrix24_event_handler_url,
            )

            # Mark installation as ready only after all setup operations succeed.
            service.mark_installation_ready(portal)

        elif isinstance(event, AppUninstallEvent):
            service.handle_app_uninstall(event)

    except (InvalidApplicationToken, Bitrix24InstallationValidationError) as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except Bitrix24OAuthError as exc:
        # The authorization server rejected the supplied installation token.
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except ValueError as exc:
        if isinstance(event, AppUninstallEvent):
            raise HTTPException(status_code=403, detail="Forbidden") from exc

        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Bitrix24EventAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to register Bitrix24 event handler.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to communicate with Bitrix24 services.",
        ) from exc

    return {"status": "ok"}
