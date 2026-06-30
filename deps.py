"""Shared FastAPI dependencies: current-user resolution and access enforcement."""

import logging

from fastapi import Depends, HTTPException, Request, status

from app.auth import AuthenticatedUser
from app.security import get_session

logger = logging.getLogger("sybase_unlock_portal.deps")


def get_current_user(request: Request) -> AuthenticatedUser:
    """
    Resolve the currently authenticated user from the signed session cookie.
    Raises 401 (handled by main.py to redirect to /login) if not authenticated.
    """
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return AuthenticatedUser(
        username=session["username"],
        display_name=session.get("display_name", session["username"]),
        roles=session.get("roles", []),
    )


def require_dba(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Dependency that enforces the DBA role (RBAC) for unlock operations."""
    if not user.is_dba:
        logger.warning("User '%s' attempted DBA action without sufficient role.", user.username)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
    return user


def get_client_ip(request: Request) -> str:
    """Best-effort extraction of the client IP, honoring a trusted proxy header if present."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
