"""Tests for the Sybase unlock workflow (using the mock connector)."""

from app.services.sybase_service import (
    MockSybaseConnector,
    is_protected_login,
    unlock_user,
)


def test_protected_login_is_rejected():
    success, message, _ = unlock_user("PRODSYB01", "sa")
    assert success is False
    assert "protected" in message.lower()


def test_protected_login_case_insensitive():
    assert is_protected_login("SA") is True
    assert is_protected_login("Sso_Role") is True
    assert is_protected_login("jsmith") is False


def test_unlock_nonexistent_login():
    success, message, _ = unlock_user("PRODSYB01", "doesnotexist")
    assert success is False
    assert "does not exist" in message.lower()


def test_unlock_already_unlocked_login():
    # 'mpatel' is seeded as already unlocked in MockSybaseConnector
    success, message, _ = unlock_user("PRODSYB01", "mpatel")
    assert success is False
    assert "already unlocked" in message.lower()


def test_unlock_locked_login_succeeds():
    connector = MockSybaseConnector()
    # Reset state for isolation since the mock store is a class attribute
    connector._mock_logins["jsmith"] = True
    success, message, elapsed = unlock_user("PRODSYB01", "jsmith")
    assert success is True
    assert "successfully unlocked" in message.lower()
    assert elapsed > 0


def test_unlock_twice_second_attempt_reports_already_unlocked():
    connector = MockSybaseConnector()
    connector._mock_logins["appuser1"] = True
    first_success, _, _ = unlock_user("PRODSYB01", "appuser1")
    second_success, second_message, _ = unlock_user("PRODSYB01", "appuser1")
    assert first_success is True
    assert second_success is False
    assert "already unlocked" in second_message.lower()
