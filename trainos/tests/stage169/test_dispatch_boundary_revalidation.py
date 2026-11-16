"""Dispatch-boundary revalidation is fail-closed within shared store objects."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_journal_consistency import (
    ExecutionJournalConsistencyChecker,
    JournalConsistencyStatus,
)
from kernel.command.execution.execution_progress import ExecutionProgress
from kernel.command.execution.execution_status import ExecutionStatus


def _execution(status, attempts=0):
    return CommandExecution(
        execution_id="dispatch-exec",
        command_id="inspect_sensor",
        progress=ExecutionProgress(attempts=attempts, max_attempts=3, completed=False),
        status=status,
    )


def _stores(tmp_path):
    idem = CommandIdempotencyStore(tmp_path / "idem.sqlite3")
    audit = ExecutionAuditStore(tmp_path / "audit.sqlite3")
    idem.claim("dispatch-key", "inspect_sensor", {"sensor": "S-1"}, execution_id="dispatch-exec")
    audit.append(_execution(ExecutionStatus.CREATED))
    return idem, audit


def test_boundary_rechecks_state_changed_after_prior_inspection(tmp_path):
    idem, audit = _stores(tmp_path)
    try:
        checker = ExecutionJournalConsistencyChecker(idem, audit)
        stale = checker.inspect("dispatch-key")
        assert stale.may_dispatch
        idem.mark_unknown("dispatch-key", "acknowledgement lost")
        calls = []

        outcome = checker.dispatch_if_consistent("dispatch-key", lambda report: calls.append(report))

        assert outcome.dispatched is False
        assert outcome.report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert calls == []
    finally:
        idem.close()
        audit.close()


def test_shared_store_transition_waits_until_dispatch_callback_exits(tmp_path):
    idem, audit = _stores(tmp_path)
    callback_entered = Event()
    allow_callback_exit = Event()
    transition_finished = Event()
    calls = []
    try:
        checker = ExecutionJournalConsistencyChecker(idem, audit)

        def dispatch(_report):
            calls.append("dispatched")
            callback_entered.set()
            assert allow_callback_exit.wait(3)
            return "accepted"

        def transition():
            assert callback_entered.wait(3)
            idem.mark_unknown("dispatch-key", "external result became uncertain")
            transition_finished.set()

        with ThreadPoolExecutor(max_workers=2) as pool:
            dispatch_future = pool.submit(checker.dispatch_if_consistent, "dispatch-key", dispatch)
            transition_future = pool.submit(transition)
            assert callback_entered.wait(3)
            # The writer uses the same store instance, so its mutation cannot
            # interleave between final validation and callback completion.
            assert not transition_finished.wait(0.1)
            allow_callback_exit.set()
            outcome = dispatch_future.result(timeout=3)
            transition_future.result(timeout=3)

        assert outcome.dispatched is True
        assert outcome.result == "accepted"
        assert calls == ["dispatched"]
        assert idem.get("dispatch-key").status.value == "unknown"
    finally:
        allow_callback_exit.set()
        idem.close()
        audit.close()


def test_non_dispatchable_report_never_invokes_callback(tmp_path):
    idem, audit = _stores(tmp_path)
    try:
        idem.mark_unknown("dispatch-key", "outcome unknown")
        checker = ExecutionJournalConsistencyChecker(idem, audit)
        calls = []
        outcome = checker.dispatch_if_consistent("dispatch-key", lambda report: calls.append(report))
        assert not outcome.dispatched
        assert outcome.report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert calls == []
    finally:
        idem.close()
        audit.close()
