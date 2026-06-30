"""ORM models for the audit database."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """One row per unlock request (successful or not)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    requester: Mapped[str] = mapped_column(String(128), index=True)
    server: Mapped[str] = mapped_column(String(128), index=True)
    login_name: Mapped[str] = mapped_column(String(128), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))  # SUCCESS | FAILED | DENIED
    message: Mapped[str] = mapped_column(Text, default="")
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    client_ip: Mapped[str] = mapped_column(String(64), default="")


class LoginAttempt(Base):
    """Tracks authentication attempts for brute-force protection and audit."""

    __tablename__ = "login_attempt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    username: Mapped[str] = mapped_column(String(128), index=True)
    success: Mapped[bool] = mapped_column(default=False)
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
