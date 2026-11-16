from tests.sqlite_resource_helpers import managed_sqlite_connection
"""Damaged durable journals must fail closed after application restart."""
import sqlite3

from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_journal_consistency import (
    ExecutionJournalConsistencyChecker,
    JournalConsistencyStatus,
)


def test_corrupt_idempotency_fingerprint_after_reopen_blocks_dispatch(tmp_path):
    path = tmp_path / "idempotency.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("key-1", "open_door", {"door": 7}, execution_id="exec-1")
    store.close()

    with managed_sqlite_connection(path) as connection:
        connection.execute(
            "UPDATE command_idempotency SET fingerprint = ? WHERE idempotency_key = ?",
            ("not-a-valid-sha256", "key-1"),
        )

    reopened = CommandIdempotencyStore(path)
    audit = ExecutionAuditStore(tmp_path / "audit.sqlite3")
    try:
        report = ExecutionJournalConsistencyChecker(reopened, audit).inspect("key-1")
        assert report.status is JournalConsistencyStatus.CONFLICT
        assert report.idempotency_status == "corrupt"
        assert not report.may_dispatch
        assert "could not be read safely" in report.reason
    finally:
        reopened.close()
        audit.close()


def test_unreadable_audit_database_blocks_dispatch_without_repair(tmp_path):
    idem_path = tmp_path / "idempotency.sqlite3"
    audit_path = tmp_path / "audit.sqlite3"
    idem = CommandIdempotencyStore(idem_path)
    idem.claim("key-2", "start_motor", {"motor": 2}, execution_id="exec-2")
    idem.close()

    damaged_audit = ExecutionAuditStore(audit_path)
    with managed_sqlite_connection(audit_path) as connection:
        connection.execute("DROP TABLE execution_audit")

    reopened_idem = CommandIdempotencyStore(idem_path)
    try:
        report = ExecutionJournalConsistencyChecker(reopened_idem, damaged_audit).inspect("key-2")
        assert report.status is JournalConsistencyStatus.CONFLICT
        assert not report.may_dispatch
        assert "could not be read safely" in report.reason
        assert reopened_idem.get("key-2").status.value == "claimed"
    finally:
        reopened_idem.close()
        damaged_audit.close()
