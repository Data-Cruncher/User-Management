"""Unlock-user workflow routes and audit history search."""

import logging

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser
from app.config import get_settings
from app.database import get_db
from app.deps import get_client_ip, require_dba
from app.schemas import UnlockRequest
from app.security import generate_csrf_token, set_csrf_cookie, validate_csrf
from app.services.audit_service import record_audit_event, search_audit_log
from app.services.sybase_service import unlock_user

logger = logging.getLogger("sybase_unlock_portal.routes.unlock")
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/unlock", response_class=HTMLResponse)
async def unlock_form(request: Request, user: AuthenticatedUser = Depends(require_dba)):
    settings = get_settings()
    csrf_token = generate_csrf_token()
    response = templates.TemplateResponse(
        "unlock.html",
        {"request": request, "user": user, "servers": settings.server_list, "csrf_token": csrf_token},
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/unlock", response_class=JSONResponse)
async def unlock_submit(
    request: Request,
    server_name: str = Form(...),
    login_name: str = Form(...),
    reason: str = Form(...),
    csrf_token: str = Form(...),
    user: AuthenticatedUser = Depends(require_dba),
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)

    if not validate_csrf(request, csrf_token):
        logger.warning("CSRF validation failed on unlock submit by '%s' from %s", user.username, client_ip)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Invalid or expired form submission. Please reload the page."},
        )

    settings = get_settings()
    if server_name not in settings.server_list:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Invalid server selection."},
        )

    try:
        payload = UnlockRequest(server_name=server_name, login_name=login_name, reason=reason)
    except ValidationError as exc:
        first_error = exc.errors()[0]["msg"]
        record_audit_event(
            db, user.username, server_name, login_name, reason,
            status="DENIED", message=f"Validation failed: {first_error}",
            execution_time_ms=0.0, client_ip=client_ip,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": first_error},
        )

    success, message, elapsed_ms = unlock_user(payload.server_name, payload.login_name)

    record_audit_event(
        db,
        requester=user.username,
        server=payload.server_name,
        login_name=payload.login_name,
        reason=payload.reason,
        status="SUCCESS" if success else "FAILED",
        message=message,
        execution_time_ms=elapsed_ms,
        client_ip=client_ip,
    )

    status_code = status.HTTP_200_OK if success else status.HTTP_422_UNPROCESSABLE_ENTITY
    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,
            "message": message,
            "login_name": payload.login_name,
            "server_name": payload.server_name,
            "execution_time_ms": round(elapsed_ms, 2),
        },
    )


@router.get("/audit", response_class=HTMLResponse)
async def audit_history(
    request: Request,
    requester: str = "",
    login_name: str = "",
    server: str = "",
    status_filter: str = "",
    user: AuthenticatedUser = Depends(require_dba),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    entries = search_audit_log(
        db,
        requester=requester or None,
        login_name=login_name or None,
        server=server or None,
        status=status_filter or None,
        limit=200,
    )
    csrf_token = generate_csrf_token()
    response = templates.TemplateResponse(
        "audit.html",
        {
            "request": request,
            "user": user,
            "entries": entries,
            "servers": settings.server_list,
            "filters": {
                "requester": requester,
                "login_name": login_name,
                "server": server,
                "status_filter": status_filter,
            },
            "csrf_token": csrf_token,
        },
    )
    set_csrf_cookie(response, csrf_token)
    return response
