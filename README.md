# Sybase ASE User Unlock Portal

An enterprise-grade, self-service web application that lets authorized DBA
users unlock Sybase ASE login accounts without manually running
`sp_locklogin` from `isql`. Built with FastAPI, server-rendered Jinja2 +
Bootstrap 5, and a fully audited unlock workflow.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Features](#features)
3. [Installation](#installation)
4. [Configuration / Environment Variables](#configuration--environment-variables)
5. [Running Locally](#running-locally)
6. [Docker Deployment](#docker-deployment)
7. [Production Deployment](#production-deployment)
8. [Security Recommendations](#security-recommendations)
9. [Testing](#testing)
10. [Troubleshooting](#troubleshooting)
11. [Future Enhancements](#future-enhancements)

---

## Architecture

```
                         ┌─────────────────────────┐
                         │        Browser           │
                         │  (DBA / Viewer user)     │
                         └────────────┬─────────────┘
                                      │ HTTPS
                                      ▼
                         ┌─────────────────────────┐
                         │   FastAPI Application     │
                         │  ─────────────────────── │
                         │  routes/login.py          │──▶ auth.py ──▶ LDAP / Mock LDAP
                         │  routes/dashboard.py      │
                         │  routes/unlock.py         │──▶ services/sybase_service.py ──▶ Sybase ASE (pyodbc) / Mock
                         │                            │──▶ services/audit_service.py ──▶ SQLite (audit.db)
                         │  security.py (CSRF, session)
                         └────────────┬───────────────┘
                                      │
                          ┌───────────┴────────────┐
                          ▼                         ▼
                 logs/app.log (rotating)     logs/audit.db (SQLite)
```

**Request flow for an unlock:**
`Browser form submit → CSRF validation → RBAC check (DBA role) → Pydantic
validation (login name format, reason length) → protected-login check →
Sybase connector (status check, then sp_locklogin) → audit record written →
JSON response → toast notification in UI.`

---

## Features

- **Authentication**: LDAP/Active Directory-ready (`app/auth.py`), with a
  mock backend enabled out of the box so the app runs without a real
  directory server.
- **RBAC**: Only users in the configured DBA group (`DBA_GROUP_NAME`) can
  reach `/unlock` and `/audit`; all authenticated users can view the
  dashboard.
- **CSRF protection**: Double-submit cookie pattern, signed with
  `itsdangerous`.
- **Session management**: Signed, `HttpOnly`, `SameSite=Lax` cookies with a
  configurable timeout (`SESSION_MAX_AGE_MINUTES`).
- **Brute-force protection**: Failed login attempts are tracked in the audit
  database; accounts are temporarily locked after `MAX_LOGIN_ATTEMPTS`.
- **Input validation**: Login names are validated against a strict regex;
  free-text reason fields are screened for script/HTML injection; all
  Sybase queries use parameterized statements.
- **Protected logins**: `sa`, `sso_role`, and other configured system
  accounts can never be unlocked through the portal.
- **Full audit trail**: Every request (successful, failed, or denied) is
  recorded with timestamp, requester, server, login, reason, status,
  execution time, and client IP — searchable from the Audit History page.
- **Rotating logs**: Application logs rotate automatically
  (`LOG_MAX_BYTES` / `LOG_BACKUP_COUNT`).
- **Modern UI**: Bootstrap 5, dark mode toggle, confirmation modal before any
  unlock, loading spinner, toast notifications.
- **Docker-ready**: `Dockerfile` + `docker-compose.yml` included.

---

## Installation

### Prerequisites

- Python 3.12+
- (Optional, for real Sybase connectivity) FreeTDS + unixODBC and `pyodbc`
- (Optional, for real LDAP) `ldap3`

### Steps

```bash
git clone <your-internal-repo-url> sybase_unlock_portal
cd sybase_unlock_portal
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set SECRET_KEY / CSRF_SECRET (see below) and other values
```

Generate strong secrets:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Configuration / Environment Variables

All configuration is loaded from environment variables (or a `.env` file)
via `app/config.py`. See `.env.example` for the full list with inline
documentation. Key variables:

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs session cookies | **required, no default** |
| `CSRF_SECRET` | Signs CSRF tokens | **required, no default** |
| `SESSION_MAX_AGE_MINUTES` | Idle session timeout | `30` |
| `MAX_LOGIN_ATTEMPTS` / `LOGIN_LOCKOUT_MINUTES` | Brute-force protection | `5` / `15` |
| `LDAP_ENABLED` / `LDAP_USE_MOCK` | Toggle real vs. mock directory auth | `false` / `true` |
| `SYBASE_SERVERS` | Comma-separated list of server aliases shown in the UI | `PRODSYB01,PRODSYB02,UATSYB01` |
| `SYBASE_USE_MOCK` | Toggle real pyodbc connection vs. in-memory demo data | `true` |
| `SYBASE_USERNAME` / `SYBASE_PASSWORD` | Least-privilege service account credentials | — |
| `PROTECTED_LOGINS` | Logins that can never be unlocked via the portal | `sa,sso_role,sybase,probe,replication_user,dbo` |
| `AUDIT_DB_URL` | SQLAlchemy URL for the audit store | `sqlite:///./logs/audit.db` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

---

## Running Locally

```bash
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000>. You'll be redirected to `/login`.

**Demo accounts** (mock LDAP backend, `LDAP_USE_MOCK=true`):

| Username | Password | Role |
|---|---|---|
| `dba_admin` | `ChangeMe123!` | `sybase_dba` |
| `jdoe` | `Passw0rd!` | `sybase_dba` |
| `viewer` | `ViewOnly1!` | `viewer` (read-only, no unlock access) |

The mock Sybase connector (`SYBASE_USE_MOCK=true`) seeds a few demo logins
(`jsmith`, `areyes`, `appuser1` locked; `mpatel` already unlocked) so you can
exercise the full unlock workflow without a real ASE instance.

---

## Docker Deployment

```bash
cp .env.example .env   # fill in real secrets
docker compose up --build -d
```

The container exposes port `8000` and mounts `./logs` for persistent audit
and application logs. A healthcheck hits `/healthz` every 30 seconds.

To connect to a **real** Sybase ASE server inside Docker, the image already
includes `unixodbc`, `freetds-dev`, and `tdsodbc`; set `SYBASE_USE_MOCK=false`
and configure `SYBASE_DSN_TEMPLATE` to match your FreeTDS/ODBC setup.

---

## Production Deployment

1. **Run behind a reverse proxy / load balancer** (nginx, ALB, etc.) that
   terminates TLS. Set `COOKIE_SECURE=true` once served over HTTPS.
2. **Use a process manager**: run multiple Uvicorn workers behind Gunicorn,
   e.g. `gunicorn -k uvicorn.workers.UvicornWorker -w 4 app.main:app`.
3. **Real LDAP/AD**: set `LDAP_ENABLED=true`, `LDAP_USE_MOCK=false`, install
   `ldap3`, and point `LDAP_SERVER` / `LDAP_BASE_DN` / `LDAP_USER_DN_TEMPLATE`
   at your directory service. Map AD group membership to the
   `DBA_GROUP_NAME` role for RBAC.
4. **Real Sybase connectivity**: set `SYBASE_USE_MOCK=false`, install
   `pyodbc`, and configure a FreeTDS DSN per environment. Use a
   **least-privilege service account** (`SYBASE_USERNAME`) that can only
   execute `sp_locklogin` and read `syslogins` — not a full sysadmin login.
5. **Audit database**: for multi-instance deployments, point `AUDIT_DB_URL`
   at a shared Postgres/MySQL instance rather than local SQLite.
6. **Secrets**: inject `SECRET_KEY`, `CSRF_SECRET`, and `SYBASE_PASSWORD` via
   your secrets manager (Vault, AWS Secrets Manager, Kubernetes Secrets) —
   never commit them.
7. **Logging**: ship `logs/app.log` to a centralized log aggregator
   (Splunk, ELK, etc.) for long-term retention and alerting.

---

## Security Recommendations

- Rotate `SECRET_KEY` and `CSRF_SECRET` periodically; rotating either
  invalidates all active sessions.
- Keep `PROTECTED_LOGINS` in sync with your actual system/service accounts.
- Review the audit log regularly (or wire `audit_service.record_audit_event`
  into a SIEM) for unusual unlock patterns.
- Enforce MFA at the LDAP/AD layer — this portal delegates authentication
  entirely to the directory service.
- Run periodic dependency audits (`pip-audit` or similar) given this app
  handles privileged database operations.
- Restrict network access to the portal to your internal network/VPN; it is
  not designed to be internet-facing.

---

## Testing

```bash
pip install -r requirements.txt
pytest -v
```

Test coverage includes:

- `tests/test_auth.py` — mock LDAP auth, RBAC, brute-force lockout
- `tests/test_validation.py` — Pydantic schema validation, injection rejection
- `tests/test_unlock.py` — protected-login rejection, not-found, already-unlocked, success path
- `tests/test_audit.py` — audit record persistence and search/filtering
- `tests/test_config.py` — settings parsing and required-field enforcement

> **Note:** This environment generated the code without outbound network
> access, so dependencies could not be `pip install`-ed or `pytest` actually
> executed here. All files were syntax-checked with `python -m py_compile`.
> Run `pip install -r requirements.txt && pytest -v` in your own environment
> to execute the suite.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `pydantic_core.ValidationError: secret_key Field required` on startup | `.env` missing or `SECRET_KEY`/`CSRF_SECRET` not set | Copy `.env.example` to `.env` and fill in values |
| Login always fails | Using real LDAP but `LDAP_USE_MOCK` still `true`, or wrong demo credentials | Check `.env`; use documented demo accounts in mock mode |
| "Could not connect to server" on unlock | `SYBASE_USE_MOCK=false` but ODBC/DSN misconfigured | Verify `SYBASE_DSN_TEMPLATE`, FreeTDS install, and network/firewall access to the ASE port |
| 403 on `/unlock` or `/audit` | Logged-in user lacks the DBA role | Confirm AD group maps to `DBA_GROUP_NAME`, or use `dba_admin` in mock mode |
| Session logs you out quickly | `SESSION_MAX_AGE_MINUTES` set low | Increase the value in `.env` |
| CSRF errors on form submit | Stale browser tab open across an app restart (secret rotated) | Reload the page to obtain a fresh CSRF token |

---

## Future Enhancements

- Multi-step approval workflow (requester + approver) for production servers
- Slack/Teams/email notifications on unlock events
- Scheduled automatic re-lock policies
- Per-server RBAC (not just a single global DBA role)
- REST API + API-key auth for automation/ChatOps integration
- Pluggable audit sinks (Splunk HEC, Elasticsearch) in addition to SQLite
- Multi-factor confirmation step before high-risk unlocks
