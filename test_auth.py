"""Tests for authentication, RBAC, and brute-force protection."""

from app.auth import (
    BruteForceGuard,
    MockLDAPBackend,
    authenticate_user,
    get_ldap_backend,
    require_role,
)
from app.config import get_settings


def test_mock_ldap_valid_credentials():
    backend = MockLDAPBackend()
    user = backend.authenticate("dba_admin", "ChangeMe123!")
    assert user is not None
    assert user.username == "dba_admin"
    assert "sybase_dba" in user.roles


def test_mock_ldap_invalid_password():
    backend = MockLDAPBackend()
    assert backend.authenticate("dba_admin", "wrongpassword") is None


def test_mock_ldap_unknown_user():
    backend = MockLDAPBackend()
    assert backend.authenticate("nonexistent_user", "whatever") is None


def test_get_ldap_backend_returns_mock_by_default():
    settings = get_settings()
    backend = get_ldap_backend(settings)
    assert isinstance(backend, MockLDAPBackend)


def test_require_role_true_and_false():
    backend = MockLDAPBackend()
    dba_user = backend.authenticate("dba_admin", "ChangeMe123!")
    viewer_user = backend.authenticate("viewer", "ViewOnly1!")
    assert require_role(dba_user, "sybase_dba") is True
    assert require_role(viewer_user, "sybase_dba") is False


def test_is_dba_property():
    backend = MockLDAPBackend()
    dba_user = backend.authenticate("dba_admin", "ChangeMe123!")
    viewer_user = backend.authenticate("viewer", "ViewOnly1!")
    assert dba_user.is_dba is True
    assert viewer_user.is_dba is False


def test_authenticate_user_success(db_session):
    user = authenticate_user(db_session, "dba_admin", "ChangeMe123!", "127.0.0.1")
    assert user is not None
    assert user.username == "dba_admin"


def test_authenticate_user_failure_records_attempt(db_session):
    user = authenticate_user(db_session, "dba_admin", "wrong", "127.0.0.1")
    assert user is None
    from app.models import LoginAttempt
    attempts = db_session.query(LoginAttempt).all()
    assert len(attempts) == 1
    assert attempts[0].success is False


def test_brute_force_lockout_after_max_attempts(db_session):
    settings = get_settings()
    guard = BruteForceGuard(db_session, settings)

    for _ in range(settings.max_login_attempts):
        guard.record_attempt("someuser", success=False, client_ip="10.0.0.1")

    assert guard.is_locked_out("someuser") is True


def test_brute_force_not_locked_out_below_threshold(db_session):
    settings = get_settings()
    guard = BruteForceGuard(db_session, settings)

    for _ in range(settings.max_login_attempts - 1):
        guard.record_attempt("anotheruser", success=False, client_ip="10.0.0.1")

    assert guard.is_locked_out("anotheruser") is False


def test_locked_out_user_cannot_authenticate_even_with_correct_password(db_session):
    settings = get_settings()
    guard = BruteForceGuard(db_session, settings)
    for _ in range(settings.max_login_attempts):
        guard.record_attempt("dba_admin", success=False, client_ip="10.0.0.1")

    user = authenticate_user(db_session, "dba_admin", "ChangeMe123!", "10.0.0.1")
    assert user is None
