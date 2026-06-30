"""
Authentication and authorization.

Provides:
- An LDAP/Active Directory authenticator with a pluggable backend. A mock
  backend is used when LDAP is not configured/available, so the app remains
  fully runnable out of the box.
- Role-Based Access Control (RBAC) helpers.
- Brute-force login protection backed by the audit database.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import LoginAttempt

logger = logging.getLogger("sybase_unlock_portal.auth")


@dataclass
class AuthenticatedUser:
    """Represents a successfully authenticated user and their roles."""

    username: str
    display_name: str
    roles: List[str] = field(default_factory=list)

    @property
    def is_dba(self) -> bool:
        settings = get_settings()
        return settings.dba_group_name in self.roles


class LDAPBackend(Protocol):
    """Protocol that any LDAP backend implementation must satisfy."""

    def authenticate(self, username: str, password: str) -> Optional[AuthenticatedUser]:
        ...


class MockLDAPBackend:
    """
    In-memory mock LDAP backend used for local development/demo purposes
    when a real directory service is not available.

    Replace with `RealLDAPBackend` (using e.g. `ldap3`) in production by
    setting LDAP_USE_MOCK=false and LDAP_ENABLED=true in the environment.
    """

    # username -> (password, display_name, roles)
    _users = {
        "dba_admin": ("ChangeMe123!", "DBA Administrator", ["sybase_dba"]),
        "jdoe": ("Passw0rd!", "John Doe", ["sybase_dba"]),
        "viewer": ("ViewOnly1!", "Read Only User", ["viewer"]),
    }

    def authenticate(self, username: str, password: str) -> Optional[AuthenticatedUser]:
        record = self._users.get(username)
        if not record:
            return None
        expected_password, display_name, roles = record
        if password != expected_password:
            return None
        return AuthenticatedUser(username=username, display_name=display_name, roles=roles)


class RealLDAPBackend:
    """
    Production LDAP/Active Directory backend skeleton using `ldap3`.

    Install with: pip install ldap3
    This is provided as a ready-to-use integration point; it performs a real
    bind against the configured LDAP server and maps group membership to
    application roles.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def authenticate(self, username: str, password: str) -> Optional[AuthenticatedUser]:
        try:
            from ldap3 import ALL, Connection, Server  # type: ignore
        except ImportError:
            logger.error("ldap3 package is not installed; cannot perform real LDAP auth.")
            return None

        user_dn = self.settings.ldap_user_dn_template.format(username=username)
        try:
            server = Server(self.settings.ldap_server, get_info=ALL)
            conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LDAP bind failed for user '%s': %s", username, exc)
            return None

        try:
            conn.search(
                search_base=self.settings.ldap_base_dn,
                search_filter=f"(uid={username})",
                attributes=["cn", "memberOf"],
            )
            if not conn.entries:
                return None
            entry = conn.entries[0]
            display_name = str(entry.cn) if hasattr(entry, "cn") else username
            groups_raw = entry.memberOf.values if hasattr(entry, "memberOf") else []
            roles = [g.split(",")[0].split("=")[-1] for g in groups_raw]
            return AuthenticatedUser(username=username, display_name=display_name, roles=roles)
        finally:
            conn.unbind()


def get_ldap_backend(settings: Optional[Settings] = None) -> LDAPBackend:
    """Factory that returns the configured LDAP backend (mock or real)."""
    settings = settings or get_settings()
    if settings.ldap_enabled and not settings.ldap_use_mock:
        return RealLDAPBackend(settings)
    return MockLDAPBackend()


class BruteForceGuard:
    """Tracks failed login attempts and enforces temporary lockouts."""

    def __init__(self, db: Session, settings: Optional[Settings] = None):
        self.db = db
        self.settings = settings or get_settings()

    def is_locked_out(self, username: str) -> bool:
        window_start = datetime.utcnow() - timedelta(minutes=self.settings.login_lockout_minutes)
        failed_count = (
            self.db.query(func.count(LoginAttempt.id))
            .filter(
                LoginAttempt.username == username,
                LoginAttempt.success.is_(False),
                LoginAttempt.timestamp >= window_start,
            )
            .scalar()
        )
        return bool(failed_count and failed_count >= self.settings.max_login_attempts)

    def record_attempt(self, username: str, success: bool, client_ip: str, detail: str = "") -> None:
        attempt = LoginAttempt(
            timestamp=datetime.utcnow(),
            username=username,
            success=success,
            client_ip=client_ip,
            detail=detail,
        )
        self.db.add(attempt)
        self.db.commit()


def authenticate_user(
    db: Session, username: str, password: str, client_ip: str
) -> Optional[AuthenticatedUser]:
    """
    Authenticate a user against the configured LDAP backend, enforcing
    brute-force lockout and recording the attempt for audit purposes.
    """
    settings = get_settings()
    guard = BruteForceGuard(db, settings)

    if guard.is_locked_out(username):
        logger.warning("Login blocked due to lockout for user '%s' from %s", username, client_ip)
        guard.record_attempt(username, success=False, client_ip=client_ip, detail="locked_out")
        return None

    backend = get_ldap_backend(settings)
    user = backend.authenticate(username, password)

    guard.record_attempt(
        username,
        success=user is not None,
        client_ip=client_ip,
        detail="ok" if user else "invalid_credentials",
    )

    if user is None:
        logger.warning("Failed login attempt for user '%s' from %s", username, client_ip)
    else:
        logger.info("Successful login for user '%s' from %s", username, client_ip)

    return user


def require_role(user: AuthenticatedUser, role: str) -> bool:
    """RBAC check: does the user have the given role?"""
    return role in user.roles
