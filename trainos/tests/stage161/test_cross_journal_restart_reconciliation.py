"""Cross-journal recovery must fail closed after a process restart."""

from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyStatus,
)
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_journal_consistency import (
    ExecutionJournalConsistencyChecker,
    JournalConsistencyStatus,
)
from kernel.command.execution.execution_progress import ExecutionProgress
from kernel.command.execution.execution_status import ExecutionStatus


def _execution(execution_id: str, command_id: str, status: ExecutionStatus) -> CommandExecution:
    return CommandExecution(
        execution_id=execution_id,
        command_id=command_id,
        progress=ExecutionProgress(
            attempts=1,
            max_attempts=3,
            completed=status is ExecutionStatus.COMPLETED,
        ),
        status=status,
    )


def _stores(tmp_path):
    return (
        CommandIdempotencyStore(tmp_path / "idempotency.sqlite3"),
        ExecutionAuditStore(tmp_path / "execution.sqlite3"),
    )


def test_running_execution_becomes_recovery_required_after_restart_without_replay(tmp_path):
    idem, audit = _stores(tmp_path)
    claim = idem.claim("key-161", "inspect_subsystem", {"name": "brakes"}, execution_id="exec-161")
    assert claim.created
    audit.append(_execution("exec-161", "inspect_subsystem", ExecutionStatus.CREATED))
    audit.append(_execution("exec-161", "inspect_subsystem", ExecutionStatus.RUNNING))
    idem.close()
    audit.close()

    idem, audit = _stores(tmp_path)
    try:
        recovered = audit.recover_incomplete_executions()
        assert len(recovered) == 1
        assert recovered[0].status is ExecutionStatus.RECOVERY_REQUIRED

        report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key-161")
        assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert not report.may_dispatch

        repeated = idem.claim(
            "key-161", "inspect_subsystem", {"name": "brakes"}, execution_id="exec-161"
        )
        assert not repeated.created
        assert repeated.record.status is IdempotencyStatus.CLAIMED
        assert len(audit.get_history("exec-161")) == 3
        assert audit.get_history("exec-161")[-1]["status"] == "recovery_required"
    finally:
        idem.close()
        audit.close()


def test_completed_execution_and_claimed_idempotency_after_restart_require_reconciliation(tmp_path):
    idem, audit = _stores(tmp_path)
    idem.claim("key-161b", "inspect_subsystem", {"name": "doors"}, execution_id="exec-161b")
    audit.append(_execution("exec-161b", "inspect_subsystem", ExecutionStatus.CREATED))
    audit.append(_execution("exec-161b", "inspect_subsystem", ExecutionStatus.RUNNING))
    audit.append(_execution("exec-161b", "inspect_subsystem", ExecutionStatus.COMPLETED))
    idem.close()
    audit.close()

    idem, audit = _stores(tmp_path)
    try:
        report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key-161b")
        assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert not report.may_dispatch
        record = idem.get("key-161b")
        assert record is not None and record.status is IdempotencyStatus.CLAIMED
        assert [row["status"] for row in audit.get_history("exec-161b")] == [
            "created", "running", "completed"
        ]
    finally:
        idem.close()
        audit.close()


def test_unknown_idempotency_remains_blocked_even_if_audit_reports_completion(tmp_path):
    idem, audit = _stores(tmp_path)
    idem.claim("key-161c", "inspect_subsystem", {"name": "traction"}, execution_id="exec-161c")
    idem.mark_unknown("key-161c", "process ended before acknowledgement")
    audit.append(_execution("exec-161c", "inspect_subsystem", ExecutionStatus.CREATED))
    audit.append(_execution("exec-161c", "inspect_subsystem", ExecutionStatus.RUNNING))
    audit.append(_execution("exec-161c", "inspect_subsystem", ExecutionStatus.COMPLETED))
    idem.close()
    audit.close()

    idem, audit = _stores(tmp_path)
    try:
        report = ExecutionJournalConsistencyChecker(idem, audit).inspect("key-161c")
        assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert not report.may_dispatch
        assert idem.get("key-161c").status is IdempotencyStatus.UNKNOWN
        assert len(audit.get_history("exec-161c")) == 3
    finally:
        idem.close()
        audit.close()
