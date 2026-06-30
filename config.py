"""
Application configuration module.

Loads all configuration from environment variables (optionally via a .env
file) using pydantic-settings. No secrets are ever hardcoded here.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings, populated from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---
    app_name: str = Field(default="Sybase ASE User Unlock Portal")
    environment: str = Field(default="development")  # development | staging | production
    debug: bool = Field(default=False)

    # --- Security / Sessions ---
    secret_key: str = Field(..., description="Used to sign session cookies. Must be set in .env")
    session_max_age_minutes: int = Field(default=30)
    csrf_secret: str = Field(..., description="Used to sign CSRF tokens. Must be set in .env")
    cookie_secure: bool = Field(default=True)
    max_login_attempts: int = Field(default=5)
    login_lockout_minutes: int = Field(default=15)

    # --- LDAP / Active Directory ---
    ldap_enabled: bool = Field(default=False)
    ldap_server: str = Field(default="ldap://localhost:389")
    ldap_base_dn: str = Field(default="dc=example,dc=com")
    ldap_user_dn_template: str = Field(default="uid={username},ou=people,dc=example,dc=com")
    ldap_use_mock: bool = Field(default=True)

    # --- RBAC ---
    dba_group_name: str = Field(default="sybase_dba")

    # --- Sybase ASE ---
    sybase_servers: str = Field(
        default="PRODSYB01,PRODSYB02,UATSYB01",
        description="Comma separated list of available Sybase server aliases",
    )
    sybase_dsn_template: str = Field(
        default="DRIVER={{FreeTDS}};SERVER={server};PORT=5000;TDS_Version=5.0;",
        description="pyodbc connection string template; {server} is substituted",
    )
    sybase_username: str = Field(default="svc_unlock_portal")
    sybase_password: str = Field(default="")
    sybase_connect_timeout_seconds: int = Field(default=5)
    sybase_use_mock: bool = Field(
        default=True,
        description="When true, uses an in-memory mock instead of a real pyodbc connection. "
        "Set to false in production once ODBC drivers/DSNs are configured.",
    )

    # --- Protected / system logins that can never be unlocked via this tool ---
    protected_logins: str = Field(
        default="sa,sso_role,sybase,probe,replication_user,dbo"
    )

    # --- Audit database ---
    audit_db_url: str = Field(default="sqlite:///./logs/audit.db")

    # --- Logging ---
    log_dir: str = Field(default="./logs")
    log_level: str = Field(default="INFO")
    log_max_bytes: int = Field(default=5_242_880)  # 5 MB
    log_backup_count: int = Field(default=5)

    @field_validator("sybase_servers")
    @classmethod
    def _validate_servers_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("sybase_servers must contain at least one server")
        return v

    @property
    def server_list(self) -> List[str]:
        return [s.strip() for s in self.sybase_servers.split(",") if s.strip()]

    @property
    def protected_login_list(self) -> List[str]:
        return [s.strip().lower() for s in self.protected_logins.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (avoids re-parsing env on every call)."""
    return Settings()
