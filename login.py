"""Login / logout routes."""

import logging

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import authenticate_user
from app.database import get_db
from app.deps import get_client_ip
from app.security import (
    clear_session_cookie,
    generate_csrf_token,
    set_csrf_cookie,
    set_session_cookie,
    validate_csrf,
)

logger = logging.getLogger("sybase_unlock_portal.routes.login")
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    csrf_token = generate_csrf_token()
    response = templates.TemplateResponse(
        "login.html", {"request": request, "csrf_token": csrf_token, "error": None}
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)

    if not validate_csrf(request, csrf_token):
        logger.warning("CSRF validation failed on login from %s", client_ip)
        new_csrf = generate_csrf_token()
        response = templates.TemplateResponse(
            "login.html",
            {"request": request, "csrf_token": new_csrf, "error": "Invalid or expired form submission. Please try again."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        set_csrf_cookie(response, new_csrf)
        return response

    user = authenticate_user(db, username.strip(), password, client_ip)

    if not user:
        new_csrf = generate_csrf_token()
        response = templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "csrf_token": new_csrf,
                "error": "Invalid username/password, or your account is temporarily locked due to repeated failed attempts.",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        set_csrf_cookie(response, new_csrf)
        return response

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(
        response,
        {"username": user.username, "display_name": user.display_name, "roles": user.roles},
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_session_cookie(response)
    return response
