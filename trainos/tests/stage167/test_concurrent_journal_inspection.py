"""Concurrent read-only inspection must not authorize divergent recovery."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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


def test_concurrent_inspection_of_unknown_execution_never_authorizes_dispatch(tmp_path):
    idem = CommandIdempotencyStore(tmp_path / "idem.sqlite3")
    audit = ExecutionAuditStore(tmp_path / "audit.sqlite3")
    try:
        idem.claim("unknown-key", "unknown-command", {"target": 1}, execution_id="exec-unknown")
        idem.mark_unknown("unknown-key", "acknowledgement lost")
        audit.append(_created("exec-unknown", "unknown-command"))
        checker = ExecutionJournalConsistencyChecker(idem, audit)
        workers = 12
        barrier = Barrier(workers)

        def inspect_once(_):
            barrier.wait(timeout=5)
            return checker.inspect("unknown-key")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            reports = list(pool.map(inspect_once, range(workers)))

        assert len(reports) == workers
        assert all(r.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED for r in reports)
        assert all(not r.may_dispatch for r in reports)
        assert idem.get("unknown-key").status.value == "unknown"
        assert [row["status"] for row in audit.get_history("exec-unknown")] == ["created"]
    finally:
        idem.close()
        audit.close()


def test_concurrent_inspection_isolated_across_independent_commands(tmp_path):
    idem = CommandIdempotencyStore(tmp_path / "idem.sqlite3")
    audit = ExecutionAuditStore(tmp_path / "audit.sqlite3")
    try:
        for i in range(8):
            key, command, execution = f"key-{i}", f"command-{i}", f"exec-{i}"
            idem.claim(key, command, {"index": i}, execution_id=execution)
            audit.append(_created(execution, command))
        # One command requires reconciliation; the others remain pre-dispatch.
        idem.mark_unknown("key-3", "result uncertain")
        checker = ExecutionJournalConsistencyChecker(idem, audit)
        jobs = [(i % 8) for i in range(80)]
        with ThreadPoolExecutor(max_workers=16) as pool:
            reports = list(pool.map(lambda i: checker.inspect(f"key-{i}"), jobs))

        for i, report in zip(jobs, reports):
            if i == 3:
                assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
                assert not report.may_dispatch
            else:
                assert report.status is JournalConsistencyStatus.CONSISTENT
                assert report.may_dispatch
        assert idem.get("key-3").status.value == "unknown"
        assert len(audit.get_history("exec-3")) == 1
    finally:
        idem.close()
        audit.close()
