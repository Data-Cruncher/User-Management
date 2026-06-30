"""Tests for configuration loading and derived settings properties."""

import pytest

from app.config import Settings, get_settings


def test_get_settings_returns_cached_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_server_list_parses_comma_separated_values():
    settings = Settings(
        secret_key="x" * 32,
        csrf_secret="y" * 32,
        sybase_servers="SRV1, SRV2 ,SRV3",
    )
    assert settings.server_list == ["SRV1", "SRV2", "SRV3"]


def test_protected_login_list_lowercased():
    settings = Settings(
        secret_key="x" * 32,
        csrf_secret="y" * 32,
        protected_logins="SA, Sso_Role,sybase",
    )
    assert settings.protected_login_list == ["sa", "sso_role", "sybase"]


def test_empty_sybase_servers_raises_validation_error():
    with pytest.raises(ValueError):
        Settings(secret_key="x" * 32, csrf_secret="y" * 32, sybase_servers="   ")


def test_settings_requires_secret_key():
    with pytest.raises(Exception):
        Settings(csrf_secret="y" * 32)  # secret_key missing entirely


def test_defaults_are_sane():
    settings = Settings(secret_key="x" * 32, csrf_secret="y" * 32)
    assert settings.session_max_age_minutes > 0
    assert settings.max_login_attempts > 0
    assert settings.sybase_use_mock is True
