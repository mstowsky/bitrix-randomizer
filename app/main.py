"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.pages import router as pages_router
from app.core.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Подключаем маршруты приложения.
app.include_router(health_router)
app.include_router(events_router)
app.include_router(pages_router)

# Раздаём статические файлы интерфейса.
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
