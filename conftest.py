"""Shared pytest fixtures for the test suite."""

import os

os.environ.setdefault("SECRET_KEY", "test_secret_key_for_pytest_only_0123456789")
os.environ.setdefault("CSRF_SECRET", "test_csrf_secret_for_pytest_only_9876543210")
os.environ.setdefault("AUDIT_DB_URL", "sqlite:///:memory:")
os.environ.setdefault("SYBASE_USE_MOCK", "true")
os.environ.setdefault("LDAP_USE_MOCK", "true")
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base


@pytest.fixture()
def db_session():
    """Provide a fresh in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
