"""Bitrix24 application event endpoints."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.events import AppInstallEvent, AppUninstallEvent
from app.services.event_service import (
    Bitrix24EventService,
    InvalidApplicationToken,
)

router = APIRouter()

Bitrix24Event = Annotated[
    AppInstallEvent | AppUninstallEvent,
    Body(discriminator="event"),
]


@router.post("/events/bitrix24", tags=["events"])
def handle_bitrix24_event(
    event: Bitrix24Event,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Process incoming Bitrix24 application lifecycle events."""
    service = Bitrix24EventService(db)

    try:
        if isinstance(event, AppInstallEvent):
            service.handle_app_install(event)
        elif isinstance(event, AppUninstallEvent):
            service.handle_app_uninstall(event)

    except InvalidApplicationToken as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except ValueError as exc:
        if isinstance(event, AppUninstallEvent):
            raise HTTPException(status_code=403, detail="Forbidden") from exc

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "ok"}