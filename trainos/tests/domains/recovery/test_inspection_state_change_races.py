"""An inspection must not return a dispatchable stale cross-journal snapshot."""
from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_journal_consistency import (
    ExecutionJournalConsistencyChecker,
    JournalConsistencyStatus,
)
from kernel.command.execution.execution_progress import ExecutionProgress
from kernel.command.execution.execution_status import ExecutionStatus


def _execution(status: ExecutionStatus, *, attempts: int, completed: bool = False) -> CommandExecution:
    return CommandExecution(
        execution_id="exec-race",
        command_id="inspect_sensor",
        progress=ExecutionProgress(attempts=attempts, max_attempts=3, completed=completed),
        status=status,
    )


def _seed(tmp_path):
    idem = CommandIdempotencyStore(tmp_path / "idem.sqlite3")
    audit = ExecutionAuditStore(tmp_path / "audit.sqlite3")
    idem.claim("race-key", "inspect_sensor", {"sensor": "S-1"}, execution_id="exec-race")
    audit.append(_execution(ExecutionStatus.CREATED, attempts=0))
    return idem, audit


def test_idempotency_transition_during_inspection_invalidates_dispatch_report(tmp_path, monkeypatch):
    idem, audit = _seed(tmp_path)
    try:
        checker = ExecutionJournalConsistencyChecker(idem, audit)
        original = audit.get_history
        raced = False

        def get_history_with_race(execution_id):
            nonlocal raced
            history = original(execution_id)
            if not raced:
                raced = True
                idem.mark_unknown("race-key", "external acknowledgement lost during inspection")
            return history

        monkeypatch.setattr(audit, "get_history", get_history_with_race)
        report = checker.inspect("race-key")

        assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert not report.may_dispatch
        assert idem.get("race-key").status.value == "unknown"
    finally:
        idem.close()
        audit.close()


def test_audit_transition_during_inspection_invalidates_stale_created_snapshot(tmp_path, monkeypatch):
    idem, audit = _seed(tmp_path)
    try:
        checker = ExecutionJournalConsistencyChecker(idem, audit)
        original = audit.get_history
        raced = False

        def get_history_with_race(execution_id):
            nonlocal raced
            history = original(execution_id)
            if not raced:
                raced = True
                audit.append(_execution(ExecutionStatus.RUNNING, attempts=1))
            return history

        monkeypatch.setattr(audit, "get_history", get_history_with_race)
        report = checker.inspect("race-key")

        assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert not report.may_dispatch
        assert [row["status"] for row in original("exec-race")] == ["created", "running"]
    finally:
        idem.close()
        audit.close()
