"""Routes for application pages."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.portal_service import PortalService

router = APIRouter()

DB_DEPENDENCY = Depends(get_db)

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "static" / "templates"


@router.api_route(
    "/install",
    methods=["GET", "HEAD", "POST"],
    include_in_schema=False,
)
async def install_page() -> FileResponse:
    """Return the application installation page."""
    return FileResponse(TEMPLATES_DIR / "install.html")


@router.api_route(
    "/app",
    methods=["GET", "HEAD", "POST"],
    include_in_schema=False,
)
async def app_page() -> FileResponse:
    """Return the main application page."""
    return FileResponse(TEMPLATES_DIR / "app.html")


@router.get("/install/status", tags=["installation"])
def installation_status(
    member_id: Annotated[str, Query(min_length=1, max_length=255)],
    db: Session = DB_DEPENDENCY,
) -> dict[str, bool]:
    """Return whether the initial installation is complete."""
    portal = PortalService(db).get_by_member_id(member_id)

    return {"ready": bool(portal is not None and portal.is_active and portal.installation_ready)}
