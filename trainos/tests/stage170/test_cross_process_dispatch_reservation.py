"""Durable dispatch reservations prevent duplicate attempts across store instances."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_journal_consistency import (
    ExecutionJournalConsistencyChecker,
    JournalConsistencyStatus,
)
from kernel.command.execution.execution_progress import ExecutionProgress
from kernel.command.execution.execution_status import ExecutionStatus


def _execution():
    return CommandExecution(
        execution_id="shared-execution",
        command_id="inspect_sensor",
        progress=ExecutionProgress(attempts=0, max_attempts=3, completed=False),
        status=ExecutionStatus.CREATED,
    )


def _prepare(tmp_path):
    idem_path = tmp_path / "idem.sqlite3"
    audit_path = tmp_path / "audit.sqlite3"
    idem = CommandIdempotencyStore(idem_path)
    audit = ExecutionAuditStore(audit_path)
    idem.claim("shared-key", "inspect_sensor", {"sensor": "S-1"}, execution_id="shared-execution")
    audit.append(_execution())
    idem.close()
    audit.close()
    return idem_path, audit_path


def test_competing_store_instances_reserve_only_one_dispatch(tmp_path):
    idem_path, audit_path = _prepare(tmp_path)
    barrier = Barrier(8)
    calls = []
    calls_lock = Lock()

    def attempt(_index):
        idem = CommandIdempotencyStore(idem_path)
        audit = ExecutionAuditStore(audit_path)
        try:
            checker = ExecutionJournalConsistencyChecker(idem, audit)
            barrier.wait(timeout=5)

            def dispatch(_report):
                with calls_lock:
                    calls.append("called")
                return "accepted"

            return checker.dispatch_if_consistent("shared-key", dispatch)
        finally:
            idem.close()
            audit.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))

    assert sum(outcome.dispatched for outcome in outcomes) == 1
    assert calls == ["called"]
    assert sum(outcome.report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED for outcome in outcomes) >= 1
    reopened = CommandIdempotencyStore(idem_path)
    try:
        record = reopened.get("shared-key")
        assert record is not None and record.dispatch_started is True
    finally:
        reopened.close()


def test_reserved_attempt_is_not_replayed_after_reopen(tmp_path):
    idem_path, audit_path = _prepare(tmp_path)
    idem = CommandIdempotencyStore(idem_path)
    audit = ExecutionAuditStore(audit_path)
    try:
        first = ExecutionJournalConsistencyChecker(idem, audit).dispatch_if_consistent(
            "shared-key", lambda _report: "accepted"
        )
        assert first.dispatched is True
    finally:
        idem.close()
        audit.close()

    idem = CommandIdempotencyStore(idem_path)
    audit = ExecutionAuditStore(audit_path)
    try:
        calls = []
        second = ExecutionJournalConsistencyChecker(idem, audit).dispatch_if_consistent(
            "shared-key", lambda report: calls.append(report)
        )
        assert second.dispatched is False
        assert second.report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert calls == []
        assert idem.get("shared-key").dispatch_started is True
    finally:
        idem.close()
        audit.close()


def test_callback_exception_marks_outcome_unknown_and_keeps_reservation(tmp_path):
    idem_path, audit_path = _prepare(tmp_path)
    idem = CommandIdempotencyStore(idem_path)
    audit = ExecutionAuditStore(audit_path)
    try:
        checker = ExecutionJournalConsistencyChecker(idem, audit)

        def uncertain_dispatch(_report):
            raise TimeoutError("acknowledgement lost")

        try:
            checker.dispatch_if_consistent("shared-key", uncertain_dispatch)
        except TimeoutError:
            pass
        else:
            raise AssertionError("callback exception should propagate")

        record = idem.get("shared-key")
        assert record.status.value == "unknown"
        assert record.dispatch_started is True
        outcome = checker.dispatch_if_consistent("shared-key", lambda _report: None)
        assert outcome.dispatched is False
        assert outcome.report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
    finally:
        idem.close()
        audit.close()
