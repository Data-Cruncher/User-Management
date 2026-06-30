"""Tests for the audit logging service."""

from app.services.audit_service import (
    get_recent_audit_entries,
    record_audit_event,
    search_audit_log,
)


def test_record_audit_event_persists(db_session):
    entry = record_audit_event(
        db_session,
        requester="jdoe",
        server="PRODSYB01",
        login_name="jsmith",
        reason="Locked after password reset",
        status="SUCCESS",
        message="Login 'jsmith' was successfully unlocked on PRODSYB01.",
        execution_time_ms=42.5,
        client_ip="10.0.0.5",
    )
    assert entry.id is not None
    assert entry.requester == "jdoe"


def test_search_audit_log_filters_by_login_name(db_session):
    record_audit_event(db_session, "jdoe", "PRODSYB01", "jsmith", "reason one",
                        "SUCCESS", "ok", 10.0, "10.0.0.1")
    record_audit_event(db_session, "jdoe", "PRODSYB01", "areyes", "reason two",
                        "SUCCESS", "ok", 12.0, "10.0.0.1")

    results = search_audit_log(db_session, login_name="jsmith")
    assert len(results) == 1
    assert results[0].login_name == "jsmith"


def test_search_audit_log_filters_by_status(db_session):
    record_audit_event(db_session, "jdoe", "PRODSYB01", "jsmith", "r",
                        "SUCCESS", "ok", 10.0, "10.0.0.1")
    record_audit_event(db_session, "jdoe", "PRODSYB01", "areyes", "r",
                        "FAILED", "boom", 8.0, "10.0.0.1")

    failed_only = search_audit_log(db_session, status="FAILED")
    assert len(failed_only) == 1
    assert failed_only[0].status == "FAILED"


def test_get_recent_audit_entries_orders_newest_first(db_session):
    record_audit_event(db_session, "jdoe", "PRODSYB01", "user1", "r",
                        "SUCCESS", "ok", 5.0, "10.0.0.1")
    record_audit_event(db_session, "jdoe", "PRODSYB01", "user2", "r",
                        "SUCCESS", "ok", 5.0, "10.0.0.1")

    recent = get_recent_audit_entries(db_session, limit=10)
    assert len(recent) == 2
    assert recent[0].login_name == "user2"  # most recently inserted first


def test_search_audit_log_respects_limit(db_session):
    for i in range(5):
        record_audit_event(db_session, "jdoe", "PRODSYB01", f"user{i}", "r",
                            "SUCCESS", "ok", 1.0, "10.0.0.1")

    limited = search_audit_log(db_session, limit=2)
    assert len(limited) == 2
