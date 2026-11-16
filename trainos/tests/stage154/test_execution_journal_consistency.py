import pytest

from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_journal_consistency import (
    ExecutionJournalConsistencyChecker,
    JournalConsistencyStatus,
)
from kernel.command.execution.execution_progress import ExecutionProgress
from kernel.command.execution.execution_status import ExecutionStatus


def _execution(execution_id, command_id, status):
    return CommandExecution(
        execution_id=execution_id,
        command_id=command_id,
        progress=ExecutionProgress(attempts=1, max_attempts=3, completed=status is ExecutionStatus.COMPLETED),
        status=status,
    )


def _stores(tmp_path):
    return (
        CommandIdempotencyStore(tmp_path / "idempotency.sqlite3"),
        ExecutionAuditStore(tmp_path / "execution.sqlite3"),
    )


def test_claimed_and_running_journals_are_consistent_and_may_dispatch(tmp_path):
    idem, audit = _stores(tmp_path)
    idem.claim("key", "command", {"x": 1}, execution_id="exec-1")
    audit.append(_execution("exec-1", "command", ExecutionStatus.CREATED))
    audit.append(_execution("exec-1", "command", ExecutionStatus.RUNNING))
    report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")
    assert report.status is JournalConsistencyStatus.CONSISTENT
    assert report.may_dispatch
    idem.close(); audit.close()


def test_completed_execution_with_claimed_idempotency_requires_reconciliation(tmp_path):
    idem, audit = _stores(tmp_path)
    idem.claim("key", "command", {}, execution_id="exec-1")
    audit.append(_execution("exec-1", "command", ExecutionStatus.CREATED))
    audit.append(_execution("exec-1", "command", ExecutionStatus.RUNNING))
    audit.append(_execution("exec-1", "command", ExecutionStatus.COMPLETED))
    report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")
    assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
    assert not report.may_dispatch
    idem.close(); audit.close()


def test_unknown_idempotency_never_authorizes_dispatch_even_if_execution_completed(tmp_path):
    idem, audit = _stores(tmp_path)
    idem.claim("key", "command", {}, execution_id="exec-1")
    idem.mark_unknown("key", "acknowledgement lost")
    audit.append(_execution("exec-1", "command", ExecutionStatus.CREATED))
    audit.append(_execution("exec-1", "command", ExecutionStatus.RUNNING))
    audit.append(_execution("exec-1", "command", ExecutionStatus.COMPLETED))
    report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")
    assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
    assert not report.may_dispatch
    idem.close(); audit.close()


def test_completed_idempotency_with_running_execution_is_conflict(tmp_path):
    idem, audit = _stores(tmp_path)
    idem.claim("key", "command", {}, execution_id="exec-1")
    idem.complete("key", {"ok": True}, execution_id="exec-1")
    audit.append(_execution("exec-1", "command", ExecutionStatus.CREATED))
    audit.append(_execution("exec-1", "command", ExecutionStatus.RUNNING))
    report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")
    assert report.status is JournalConsistencyStatus.CONFLICT
    assert not report.may_dispatch
    idem.close(); audit.close()


def test_missing_audit_history_requires_reconciliation_and_does_not_repair(tmp_path):
    idem, audit = _stores(tmp_path)
    idem.claim("key", "command", {}, execution_id="exec-missing")
    checker = ExecutionJournalConsistencyChecker(idem, audit)
    report = checker.inspect("key")
    assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
    assert audit.get_history("exec-missing") == ()
    assert idem.get("key").status.value == "claimed"
    idem.close(); audit.close()


def test_unbound_legacy_record_is_not_dispatch_authorized(tmp_path):
    idem, audit = _stores(tmp_path)
    idem.claim("key", "command", {})
    report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")
    assert report.status is JournalConsistencyStatus.UNBOUND
    assert not report.may_dispatch
    idem.close(); audit.close()


def test_unknown_key_and_blank_key_are_rejected(tmp_path):
    idem, audit = _stores(tmp_path)
    checker = ExecutionJournalConsistencyChecker(idem, audit)
    with pytest.raises(ValueError, match="must not be empty"):
        checker.inspect(" ")
    with pytest.raises(ValueError, match="unknown idempotency key"):
        checker.inspect("missing")
    idem.close(); audit.close()
