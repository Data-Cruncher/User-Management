"""
Sybase ASE User Unlock Portal — application entrypoint.

Run locally with:
    pip install -r requirements.txt
    uvicorn app.main:app --reload
"""

import logging
import logging.handlers
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routes import dashboard, login, unlock
from app.security import add_security_headers

settings = get_settings()


def configure_logging() -> None:
    """Set up rotating file logs plus console logging."""
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    root_logger = logging.getLogger("sybase_unlock_portal")
    root_logger.setLevel(settings.log_level.upper())
    root_logger.propagate = False

    if root_logger.handlers:
        return  # avoid duplicate handlers on --reload

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
    )
    file_handler.setFormatter(logging.Formatter(log_format))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


configure_logging()
logger = logging.getLogger("sybase_unlock_portal.main")

app = FastAPI(
    title=settings.app_name,
    description="Enterprise self-service portal for unlocking Sybase ASE logins.",
    version="1.0.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(login.router, tags=["auth"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(unlock.router, tags=["unlock"])


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("Application startup complete. Environment=%s", settings.environment)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Attach standard security headers to every response."""
    response = await call_next(request)
    return add_security_headers(response)


@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """Redirect unauthenticated/unauthorized HTML requests to the login page; return JSON for API calls."""
    accepts_html = "text/html" in request.headers.get("accept", "")

    if exc.status_code == status.HTTP_401_UNAUTHORIZED and accepts_html:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if exc.status_code == status.HTTP_403_FORBIDDEN and accepts_html:
        return JSONResponse(
            status_code=403,
            content={"detail": "You do not have permission to access this resource."},
        )

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception processing request %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Please contact support."},
    )


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")


@app.get("/healthz")
async def health_check():
    """Simple liveness endpoint for load balancers / container orchestration."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}
