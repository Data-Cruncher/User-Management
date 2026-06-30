"""Tests for input validation (Pydantic schemas)."""

import pytest
from pydantic import ValidationError

from app.schemas import LoginRequest, UnlockRequest


def test_valid_unlock_request():
    req = UnlockRequest(server_name="PRODSYB01", login_name="jsmith", reason="User locked out, verified via ticket #1234")
    assert req.login_name == "jsmith"


def test_login_name_rejects_invalid_characters():
    with pytest.raises(ValidationError):
        UnlockRequest(server_name="PRODSYB01", login_name="jsmith; drop table", reason="x" * 15)


def test_login_name_rejects_leading_digit():
    with pytest.raises(ValidationError):
        UnlockRequest(server_name="PRODSYB01", login_name="1jsmith", reason="x" * 15)


def test_login_name_rejects_too_long():
    with pytest.raises(ValidationError):
        UnlockRequest(server_name="PRODSYB01", login_name="a" * 31, reason="x" * 15)


def test_reason_too_short_rejected():
    with pytest.raises(ValidationError):
        UnlockRequest(server_name="PRODSYB01", login_name="jsmith", reason="short")


def test_reason_rejects_script_injection():
    with pytest.raises(ValidationError):
        UnlockRequest(
            server_name="PRODSYB01",
            login_name="jsmith",
            reason="<script>alert('xss')</script> please unlock",
        )


def test_reason_rejects_event_handler_injection():
    with pytest.raises(ValidationError):
        UnlockRequest(
            server_name="PRODSYB01",
            login_name="jsmith",
            reason="onmouseover=alert(1) please unlock this account",
        )


def test_login_request_strips_whitespace():
    req = LoginRequest(username="  jdoe  ", password="secret")
    assert req.username == "jdoe"


def test_login_request_requires_nonempty_password():
    with pytest.raises(ValidationError):
        LoginRequest(username="jdoe", password="")
