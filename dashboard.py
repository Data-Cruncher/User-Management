"""Dashboard route."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser
from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.security import generate_csrf_token, set_csrf_cookie
from app.services.audit_service import get_recent_audit_entries

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    recent_entries = get_recent_audit_entries(db, limit=10)
    csrf_token = generate_csrf_token()

    response = templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "servers": settings.server_list,
            "recent_entries": recent_entries,
            "csrf_token": csrf_token,
        },
    )
    set_csrf_cookie(response, csrf_token)
    return response
