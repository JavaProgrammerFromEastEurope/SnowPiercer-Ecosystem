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


@pytest.mark.parametrize("audit_command_id", ["different-command", "command-with-suffix"])
def test_mismatched_audit_command_identity_fails_closed(tmp_path, audit_command_id):
    idem = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    audit = ExecutionAuditStore(tmp_path / "execution.sqlite3")
    idem.claim("key", "expected-command", {"target": "subsystem-A"}, execution_id="exec-1")
    audit.append(_execution("exec-1", audit_command_id, ExecutionStatus.CREATED))

    report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")

    assert report.status is JournalConsistencyStatus.CONFLICT
    assert not report.may_dispatch
    assert "command identity" in report.reason
    assert idem.get("key").status.value == "claimed"
    assert len(audit.get_history("exec-1")) == 1
    idem.close()
    audit.close()


def test_matching_identity_remains_consistent(tmp_path):
    idem = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    audit = ExecutionAuditStore(tmp_path / "execution.sqlite3")
    idem.claim("key", "expected-command", {"target": "subsystem-A"}, execution_id="exec-1")
    audit.append(_execution("exec-1", "expected-command", ExecutionStatus.CREATED))
    report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")
    assert report.status is JournalConsistencyStatus.CONSISTENT
    assert report.may_dispatch
    idem.close()
    audit.close()


def test_command_identity_mismatch_after_completed_audit_is_still_conflict(tmp_path):
    idem = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    audit = ExecutionAuditStore(tmp_path / "execution.sqlite3")
    idem.claim("key", "expected-command", {}, execution_id="exec-1")
    audit.append(_execution("exec-1", "different-command", ExecutionStatus.CREATED))
    # A valid state transition can be internally consistent while still belonging
    # to the wrong command identity, so the consistency checker must reject it.
    audit.append(_execution("exec-1", "different-command", ExecutionStatus.RUNNING))
    audit.append(_execution("exec-1", "different-command", ExecutionStatus.COMPLETED))
    report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")
    assert report.status is JournalConsistencyStatus.CONFLICT
    assert not report.may_dispatch
    idem.close()
    audit.close()


def test_corrupted_blank_audit_command_identity_fails_closed(tmp_path):
    idem = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    audit = ExecutionAuditStore(tmp_path / "execution.sqlite3")
    idem.claim("key", "expected-command", {}, execution_id="exec-1")
    audit.append(_execution("exec-1", "expected-command", ExecutionStatus.CREATED))
    # Simulate external database corruption that bypasses CommandExecution validation.
    audit._connection.execute(
        "UPDATE execution_audit SET command_id = '' WHERE execution_id = ?", ("exec-1",)
    )
    report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key")
    assert report.status is JournalConsistencyStatus.CONFLICT
    assert not report.may_dispatch
    assert report.reason in {"execution audit metadata is malformed", "execution audit command identity does not match idempotency record"}
    idem.close()
    audit.close()
