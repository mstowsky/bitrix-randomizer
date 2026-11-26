"""Routes for application pages."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "static" / "templates"


@router.get("/install", include_in_schema=False)
async def install_page() -> FileResponse:
    """Return the application installation page."""
    return FileResponse(TEMPLATES_DIR / "install.html")


@router.get("/app", include_in_schema=False)
async def app_page() -> FileResponse:
    """Return the main application page."""
    return FileResponse(TEMPLATES_DIR / "app.html")
