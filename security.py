"""
Security utilities: signed session cookies, CSRF token generation/validation,
and security-related HTTP headers.
"""

import logging
import secrets
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings

logger = logging.getLogger("sybase_unlock_portal.security")

SESSION_COOKIE_NAME = "sup_session"
CSRF_COOKIE_NAME = "sup_csrf"
CSRF_FORM_FIELD = "csrf_token"


def _session_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.secret_key, salt="session")


def _csrf_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.csrf_secret, salt="csrf")


def create_session_cookie(payload: dict) -> str:
    """Sign and serialize the session payload (e.g. username, roles)."""
    return _session_serializer().dumps(payload)


def read_session_cookie(token: str) -> Optional[dict]:
    """Validate and deserialize a session cookie; returns None if invalid/expired."""
    settings = get_settings()
    try:
        return _session_serializer().loads(token, max_age=settings.session_max_age_minutes * 60)
    except SignatureExpired:
        logger.info("Session expired.")
        return None
    except BadSignature:
        logger.warning("Invalid session cookie signature encountered (possible tampering).")
        return None


def set_session_cookie(response: Response, payload: dict) -> None:
    settings = get_settings()
    token = create_session_cookie(payload)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_max_age_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def get_session(request: Request) -> Optional[dict]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return read_session_cookie(token)


# --- CSRF protection (double-submit cookie pattern) ---

def generate_csrf_token() -> str:
    raw = secrets.token_urlsafe(32)
    return _csrf_serializer().dumps(raw)


def set_csrf_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=settings.session_max_age_minutes * 60,
        httponly=False,  # must be readable so it can be embedded in forms by the server template
        secure=settings.cookie_secure,
        samesite="lax",
    )


def validate_csrf(request: Request, submitted_token: str) -> bool:
    """Validate the submitted CSRF token against the cookie (double-submit pattern)."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token or not submitted_token:
        return False
    if not secrets.compare_digest(cookie_token, submitted_token):
        return False
    try:
        _csrf_serializer().loads(cookie_token, max_age=3600 * 4)
    except (BadSignature, SignatureExpired):
        return False
    return True


def add_security_headers(response: Response) -> Response:
    """Attach standard security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:;"
    )
    return response
