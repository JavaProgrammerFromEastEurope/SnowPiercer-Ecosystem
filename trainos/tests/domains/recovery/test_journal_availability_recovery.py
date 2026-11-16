"""Temporary journal unavailability must fail closed and recover read-only."""

from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_journal_consistency import (
    ExecutionJournalConsistencyChecker,
    JournalConsistencyStatus,
)
from kernel.command.execution.execution_progress import ExecutionProgress
from kernel.command.execution.execution_status import ExecutionStatus


def _created(execution_id: str, command_id: str) -> CommandExecution:
    return CommandExecution(
        execution_id=execution_id,
        command_id=command_id,
        progress=ExecutionProgress(attempts=0, max_attempts=3, completed=False),
        status=ExecutionStatus.CREATED,
    )


def test_closed_audit_store_fails_closed_then_reopened_store_recovers(tmp_path):
    idem_path = tmp_path / "idempotency.sqlite3"
    audit_path = tmp_path / "audit.sqlite3"
    idem = CommandIdempotencyStore(idem_path)
    idem.claim("key", "command", {"target": 1}, execution_id="exec-1")
    audit = ExecutionAuditStore(audit_path)
    audit.append(_created("exec-1", "command"))
    audit.close()

    checker = ExecutionJournalConsistencyChecker(idem, audit)
    unavailable = checker.inspect("key")
    assert unavailable.status is JournalConsistencyStatus.CONFLICT
    assert not unavailable.may_dispatch
    assert "could not be read safely" in unavailable.reason
    assert idem.get("key").status.value == "claimed"

    reopened_audit = ExecutionAuditStore(audit_path)
    try:
        recovered = ExecutionJournalConsistencyChecker(idem, reopened_audit).inspect("key")
        assert recovered.status is JournalConsistencyStatus.CONSISTENT
        assert recovered.may_dispatch
        assert [row["status"] for row in reopened_audit.get_history("exec-1")] == ["created"]
        assert idem.get("key").status.value == "claimed"
    finally:
        idem.close()
        reopened_audit.close()


def test_closed_idempotency_store_fails_closed_then_reopen_preserves_unknown(tmp_path):
    idem_path = tmp_path / "idempotency.sqlite3"
    audit_path = tmp_path / "audit.sqlite3"
    idem = CommandIdempotencyStore(idem_path)
    idem.claim("key", "command", {}, execution_id="exec-2")
    idem.mark_unknown("key", "result acknowledgement was lost")
    idem.close()
    audit = ExecutionAuditStore(audit_path)
    audit.append(_created("exec-2", "command"))

    unavailable = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")
    assert unavailable.status is JournalConsistencyStatus.CONFLICT
    assert not unavailable.may_dispatch

    reopened_idem = CommandIdempotencyStore(idem_path)
    try:
        recovered = ExecutionJournalConsistencyChecker(reopened_idem, audit).inspect("key")
        assert recovered.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert not recovered.may_dispatch
        assert reopened_idem.get("key").status.value == "unknown"
        assert [row["status"] for row in audit.get_history("exec-2")] == ["created"]
    finally:
        reopened_idem.close()
        audit.close()
