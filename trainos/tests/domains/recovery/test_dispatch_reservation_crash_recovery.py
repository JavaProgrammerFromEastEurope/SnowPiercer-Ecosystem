"""A reservation without a recorded outcome must never authorize replay."""
from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_journal_consistency import (
    ExecutionJournalConsistencyChecker,
    JournalConsistencyStatus,
)
from kernel.command.execution.execution_progress import ExecutionProgress
from kernel.command.execution.execution_status import ExecutionStatus


def _execution(execution_id, command_id):
    return CommandExecution(
        execution_id=execution_id,
        command_id=command_id,
        progress=ExecutionProgress(attempts=0, max_attempts=3, completed=False),
        status=ExecutionStatus.CREATED,
    )


def _prepare(tmp_path):
    idem_path = tmp_path / "idem.sqlite3"
    audit_path = tmp_path / "audit.sqlite3"
    idem = CommandIdempotencyStore(idem_path)
    audit = ExecutionAuditStore(audit_path)
    idem.claim("crashed-key", "inspect_sensor", {"sensor": "S-1"}, execution_id="exec-crashed")
    audit.append(_execution("exec-crashed", "inspect_sensor"))
    idem.claim("independent-key", "read_temperature", {"sensor": "T-2"}, execution_id="exec-independent")
    audit.append(_execution("exec-independent", "read_temperature"))
    idem.close()
    audit.close()
    return idem_path, audit_path


def test_restart_after_reservation_before_callback_requires_reconciliation(tmp_path):
    idem_path, audit_path = _prepare(tmp_path)
    idem = CommandIdempotencyStore(idem_path)
    try:
        # Simulate process death after reservation but before callback entry.
        assert idem.reserve_dispatch("crashed-key") is True
    finally:
        idem.close()

    idem = CommandIdempotencyStore(idem_path)
    audit = ExecutionAuditStore(audit_path)
    try:
        checker = ExecutionJournalConsistencyChecker(idem, audit)
        report = checker.inspect("crashed-key")
        assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert report.may_dispatch is False
        calls = []
        outcome = checker.dispatch_if_consistent("crashed-key", lambda report: calls.append(report))
        assert outcome.dispatched is False
        assert calls == []
        record = idem.get("crashed-key")
        assert record.dispatch_started is True
        assert record.status.value == "claimed"
    finally:
        idem.close()
        audit.close()


def test_crashed_reservation_does_not_block_independent_command(tmp_path):
    idem_path, audit_path = _prepare(tmp_path)
    idem = CommandIdempotencyStore(idem_path)
    try:
        assert idem.reserve_dispatch("crashed-key") is True
    finally:
        idem.close()

    idem = CommandIdempotencyStore(idem_path)
    audit = ExecutionAuditStore(audit_path)
    try:
        checker = ExecutionJournalConsistencyChecker(idem, audit)
        calls = []
        blocked = checker.dispatch_if_consistent("crashed-key", lambda report: calls.append("crashed"))
        assert blocked.dispatched is False
        assert blocked.report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED

        independent = checker.dispatch_if_consistent(
            "independent-key", lambda report: calls.append("independent") or "ok"
        )
        assert independent.dispatched is True
        assert independent.result == "ok"
        assert calls == ["independent"]
    finally:
        idem.close()
        audit.close()


def test_unknown_reserved_attempt_remains_blocked(tmp_path):
    idem_path, audit_path = _prepare(tmp_path)
    idem = CommandIdempotencyStore(idem_path)
    audit = ExecutionAuditStore(audit_path)
    try:
        assert idem.reserve_dispatch("crashed-key") is True
        idem.mark_unknown("crashed-key", "process restarted after dispatch reservation")
        report = ExecutionJournalConsistencyChecker(idem, audit).inspect("crashed-key")
        assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert report.may_dispatch is False
        assert idem.get("crashed-key").dispatch_started is True
    finally:
        idem.close()
        audit.close()
