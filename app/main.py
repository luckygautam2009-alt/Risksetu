"""
RISKSETU AI — application entrypoint.

Dependency rule (§3): routers must not contain business logic
(router → schema → service → repository → database). This file only wires
middleware, error handlers, and routers together.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

configure_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Hardening checklist: "No CORS wildcard in production configuration."
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)

# Frontend static files mount
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

if FRONTEND_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="static_assets")


@app.get("/")
def root():
    """Serves frontend index.html if built, otherwise returns API health status."""
    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))
    return {"status": "ok", "service": "risksetu-api", "docs": "/api/v1/health"}
