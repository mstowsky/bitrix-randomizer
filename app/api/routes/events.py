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
            portal = service.handle_app_install(event)

            if not settings.bitrix24_event_handler_url:
                raise HTTPException(
                    status_code=500,
                    detail="Bitrix24 event handler URL is not configured.",
                )

            event_client = Bitrix24EventClient()
            await event_client.ensure_event_handler(
                client_endpoint=event.auth.client_endpoint,
                access_token=event.auth.access_token,
                event="ONAPPUNINSTALL",
                handler=settings.bitrix24_event_handler_url,
            )

            service.mark_installation_ready(portal)

        elif isinstance(event, AppUninstallEvent):
            service.handle_app_uninstall(event)

    except InvalidApplicationToken as exc:
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
            detail="Failed to communicate with Bitrix24 REST API.",
        ) from exc

    return {"status": "ok"}
