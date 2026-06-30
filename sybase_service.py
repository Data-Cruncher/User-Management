"""
Sybase ASE interaction layer.

Implements connecting to Sybase ASE, checking login status, and unlocking
logins via `sp_locklogin`. A mock backend (`MockSybaseConnector`) is provided
so the application is fully runnable without a real ASE instance/ODBC driver
present -- set SYBASE_USE_MOCK=false in production.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Protocol

from app.config import Settings, get_settings

logger = logging.getLogger("sybase_unlock_portal.sybase")


class SybaseError(Exception):
    """Base exception for Sybase operation failures."""


class SybaseConnectionError(SybaseError):
    """Raised when a connection to the Sybase server cannot be established."""


class SybaseTimeoutError(SybaseError):
    """Raised when a Sybase operation times out."""


class LoginNotFoundError(SybaseError):
    """Raised when the requested login does not exist on the server."""


@dataclass
class LoginStatus:
    login_name: str
    exists: bool
    locked: bool


class SybaseConnector(Protocol):
    """Protocol any Sybase connector implementation must satisfy."""

    def get_login_status(self, server: str, login_name: str) -> LoginStatus:
        ...

    def unlock_login(self, server: str, login_name: str) -> None:
        ...


class PyODBCSybaseConnector:
    """
    Real Sybase ASE connector using pyodbc (or FreeTDS).

    Requires the `pyodbc` package and a working ODBC driver/DSN configured
    on the host. Connection parameters are derived from application settings
    (never hardcoded), and credentials are pulled from environment variables.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def _connect(self, server: str):
        try:
            import pyodbc  # type: ignore
        except ImportError as exc:
            raise SybaseConnectionError(
                "pyodbc is not installed. Install it or enable SYBASE_USE_MOCK."
            ) from exc

        dsn = self.settings.sybase_dsn_template.format(server=server)
        try:
            conn = pyodbc.connect(
                dsn,
                uid=self.settings.sybase_username,
                pwd=self.settings.sybase_password,
                timeout=self.settings.sybase_connect_timeout_seconds,
            )
            return conn
        except pyodbc.OperationalError as exc:
            raise SybaseTimeoutError(f"Timed out connecting to {server}.") from exc
        except Exception as exc:  # noqa: BLE001
            raise SybaseConnectionError(f"Could not connect to {server}: {exc}") from exc

    def get_login_status(self, server: str, login_name: str) -> LoginStatus:
        conn = self._connect(server)
        try:
            cursor = conn.cursor()
            # Parameterized query — never interpolate login_name directly into SQL.
            cursor.execute(
                "SELECT name, status FROM master..syslogins WHERE name = ?",
                (login_name,),
            )
            row = cursor.fetchone()
            if row is None:
                return LoginStatus(login_name=login_name, exists=False, locked=False)
            # In syslogins, the locked bit is typically bit 1 (value 2) of the status column.
            status_value = int(row.status) if row.status is not None else 0
            locked = bool(status_value & 2)
            return LoginStatus(login_name=login_name, exists=True, locked=locked)
        finally:
            conn.close()

    def unlock_login(self, server: str, login_name: str) -> None:
        conn = self._connect(server)
        try:
            cursor = conn.cursor()
            # sp_locklogin is a system procedure; the login name is passed as a
            # bound parameter, not string-concatenated, to avoid injection.
            cursor.execute("EXEC sp_locklogin ?, 'unlock'", (login_name,))
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            raise SybaseError(f"sp_locklogin failed for '{login_name}' on {server}: {exc}") from exc
        finally:
            conn.close()


class MockSybaseConnector:
    """
    In-memory mock Sybase connector for local development and demos.

    Simulates a small set of logins, some locked, some not, across the
    configured server list so the full unlock workflow can be exercised
    without a real ASE instance.
    """

    _mock_logins = {
        "jsmith": True,    # locked
        "areyes": True,    # locked
        "mpatel": False,   # already unlocked
        "appuser1": True,  # locked
    }

    def get_login_status(self, server: str, login_name: str) -> LoginStatus:
        time.sleep(0.15)  # simulate network latency
        if login_name not in self._mock_logins:
            return LoginStatus(login_name=login_name, exists=False, locked=False)
        return LoginStatus(
            login_name=login_name, exists=True, locked=self._mock_logins[login_name]
        )

    def unlock_login(self, server: str, login_name: str) -> None:
        time.sleep(0.25)  # simulate exec latency
        if login_name not in self._mock_logins:
            raise LoginNotFoundError(f"Login '{login_name}' does not exist on {server}.")
        self._mock_logins[login_name] = False


def get_connector(settings: Optional[Settings] = None) -> SybaseConnector:
    settings = settings or get_settings()
    if settings.sybase_use_mock:
        return MockSybaseConnector()
    return PyODBCSybaseConnector(settings)


def is_protected_login(login_name: str, settings: Optional[Settings] = None) -> bool:
    """Check whether a login is a protected/system account that must never be unlocked here."""
    settings = settings or get_settings()
    return login_name.strip().lower() in settings.protected_login_list


def unlock_user(server: str, login_name: str) -> tuple[bool, str, float]:
    """
    Orchestrates the full unlock workflow for a single login:
      1. Reject protected/system logins.
      2. Verify the login exists.
      3. Verify the login is currently locked.
      4. Execute sp_locklogin to unlock it.

    Returns (success, message, execution_time_ms).
    """
    settings = get_settings()
    start = time.perf_counter()

    if is_protected_login(login_name, settings):
        elapsed = (time.perf_counter() - start) * 1000
        msg = f"Login '{login_name}' is a protected system account and cannot be unlocked here."
        logger.warning(msg)
        return False, msg, elapsed

    connector = get_connector(settings)

    try:
        status = connector.get_login_status(server, login_name)
    except SybaseTimeoutError as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("Timeout checking status for '%s' on %s: %s", login_name, server, exc)
        return False, f"Connection to {server} timed out. Please try again.", elapsed
    except SybaseConnectionError as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("Connection error checking '%s' on %s: %s", login_name, server, exc)
        return False, f"Could not connect to server {server}. Contact infrastructure support.", elapsed
    except SybaseError as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("Unexpected Sybase error: %s", exc)
        return False, "An unexpected database error occurred.", elapsed

    if not status.exists:
        elapsed = (time.perf_counter() - start) * 1000
        msg = f"Login '{login_name}' does not exist on {server}."
        logger.info(msg)
        return False, msg, elapsed

    if not status.locked:
        elapsed = (time.perf_counter() - start) * 1000
        msg = f"Login '{login_name}' is already unlocked on {server}."
        logger.info(msg)
        return False, msg, elapsed

    try:
        connector.unlock_login(server, login_name)
    except LoginNotFoundError as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error(str(exc))
        return False, str(exc), elapsed
    except SybaseError as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("Unlock failed for '%s' on %s: %s", login_name, server, exc)
        return False, f"Failed to unlock '{login_name}': {exc}", elapsed
    except Exception as exc:  # noqa: BLE001
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception("Unexpected exception unlocking '%s' on %s", login_name, server)
        return False, "An unexpected error occurred while unlocking the login.", elapsed

    elapsed = (time.perf_counter() - start) * 1000
    msg = f"Login '{login_name}' was successfully unlocked on {server}."
    logger.info(msg)
    return True, msg, elapsed
