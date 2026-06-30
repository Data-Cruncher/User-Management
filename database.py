"""
Database setup for the audit trail store (SQLite by default, but any
SQLAlchemy-supported database can be used via AUDIT_DB_URL).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.audit_db_url.startswith("sqlite") else {}

engine = create_engine(settings.audit_db_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    """Base class for ORM models."""
    pass


def get_db():
    """FastAPI dependency that yields a database session and closes it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call multiple times (idempotent)."""
    # Import models so they are registered on Base.metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
