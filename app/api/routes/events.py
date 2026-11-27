"""Bitrix24 application event endpoints."""

import json
import re
from urllib.parse import parse_qs

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
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


def parse_form_payload(body: bytes) -> dict:
    """Convert URL-encoded Bitrix24 form fields into a nested dictionary."""
    decoded_body = body.decode("utf-8")
    form_data = parse_qs(decoded_body, keep_blank_values=True)

    payload = {}

    for key, values in form_data.items():
        value = values[-1]

        # Convert fields such as auth[member_id] into nested dictionaries.
        match = re.fullmatch(r"([a-zA-Z_][a-zA-Z0-9_]*)\[([a-zA-Z_][a-zA-Z0-9_]*)\]", key)

        if match:
            parent, child = match.groups()
            payload.setdefault(parent, {})[child] = value
        else:
            payload[key] = value

    return payload


async def get_event_payload(request: Request) -> dict:
    """Read an incoming event as JSON or URL-encoded form data."""
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()

    try:
        body = await request.body()

        if media_type == "application/json" or media_type.endswith("+json"):
            payload = json.loads(body)

        elif media_type == "application/x-www-form-urlencoded":
            payload = parse_form_payload(body)

        else:
            raise HTTPException(
                status_code=415,
                detail="Unsupported event content type.",
            )

    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid event request body.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=422,
            detail="Invalid Bitrix24 event payload.",
        )

    return payload


@router.post("/events/bitrix24", tags=["events"])
async def handle_bitrix24_event(
    request: Request,
    db: Session = DB_DEPENDENCY,
) -> dict[str, str]:
    """Process incoming Bitrix24 application lifecycle events."""
    payload = await get_event_payload(request)

    try:
        event_name = payload.get("event")

        if event_name == "ONAPPINSTALL":
            event = AppInstallEvent.model_validate(payload)

        elif event_name == "ONAPPUNINSTALL":
            event = AppUninstallEvent.model_validate(payload)

        else:
            raise HTTPException(
                status_code=422,
                detail="Unsupported Bitrix24 event.",
            )

    except ValidationError as exc:
        # Do not expose incoming OAuth tokens in validation error responses.
        raise HTTPException(
            status_code=422,
            detail="Invalid Bitrix24 event payload.",
        ) from exc

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
