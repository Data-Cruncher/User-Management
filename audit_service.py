"""Audit logging service: persists every unlock request and supports search."""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.schemas import AuditEntry

logger = logging.getLogger("sybase_unlock_portal.audit")


def record_audit_event(
    db: Session,
    requester: str,
    server: str,
    login_name: str,
    reason: str,
    status: str,
    message: str,
    execution_time_ms: float,
    client_ip: str,
) -> AuditLog:
    """Persist a single audit record. Always called, regardless of outcome."""
    entry = AuditLog(
        timestamp=datetime.utcnow(),
        requester=requester,
        server=server,
        login_name=login_name,
        reason=reason,
        status=status,
        message=message,
        execution_time_ms=execution_time_ms,
        client_ip=client_ip,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    logger.info(
        "AUDIT requester=%s server=%s login=%s status=%s time_ms=%.2f ip=%s",
        requester, server, login_name, status, execution_time_ms, client_ip,
    )
    return entry


def search_audit_log(
    db: Session,
    requester: Optional[str] = None,
    login_name: Optional[str] = None,
    server: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[AuditEntry]:
    """Search the audit trail with optional filters, most recent first."""
    query = db.query(AuditLog)
    if requester:
        query = query.filter(AuditLog.requester.ilike(f"%{requester}%"))
    if login_name:
        query = query.filter(AuditLog.login_name.ilike(f"%{login_name}%"))
    if server:
        query = query.filter(AuditLog.server == server)
    if status:
        query = query.filter(AuditLog.status == status)

    rows = query.order_by(desc(AuditLog.timestamp)).limit(limit).all()
    return [AuditEntry.model_validate(row) for row in rows]


def get_recent_audit_entries(db: Session, limit: int = 10) -> List[AuditEntry]:
    """Convenience helper for the dashboard's recent-activity widget."""
    return search_audit_log(db, limit=limit)
