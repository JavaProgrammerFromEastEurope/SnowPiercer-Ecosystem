"""Concurrent multi-command restart recovery must be isolated and idempotent."""
from concurrent.futures import ThreadPoolExecutor

from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
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


def test_concurrent_recovery_of_many_running_commands_appends_one_recovery_each(tmp_path):
    idem, audit = _stores(tmp_path)
    try:
        for suffix in range(8):
            key, execution_id, command = f"key-{suffix}", f"exec-{suffix}", f"command-{suffix}"
            idem.claim(key, command, {"index": suffix}, execution_id=execution_id)
            audit.append(_execution(execution_id, command, ExecutionStatus.CREATED))
            audit.append(_execution(execution_id, command, ExecutionStatus.RUNNING))

        # Several recovery workers may start at once after restart.
        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(lambda _: audit.recover_incomplete_executions(), range(6)))

        recovered_ids = [item.execution_id for batch in outcomes for item in batch]
        assert sorted(recovered_ids) == [f"exec-{i}" for i in range(8)]
        for suffix in range(8):
            history = audit.get_history(f"exec-{suffix}")
            assert [row["status"] for row in history] == ["created", "running", "recovery_required"]
            report = ExecutionJournalConsistencyChecker(idem, audit).inspect(f"key-{suffix}")
            assert report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
            assert not report.may_dispatch
    finally:
        idem.close()
        audit.close()


def test_corrupt_execution_record_does_not_prevent_independent_command_recovery(tmp_path):
    idem, audit = _stores(tmp_path)
    try:
        idem.claim("bad-key", "inspect_bad", {"unit": "X"}, execution_id="bad-exec")
        idem.claim("good-key", "inspect_good", {"unit": "Y"}, execution_id="good-exec")
        audit.append(_execution("bad-exec", "inspect_bad", ExecutionStatus.CREATED))
        audit.append(_execution("bad-exec", "inspect_bad", ExecutionStatus.RUNNING))
        audit.append(_execution("good-exec", "inspect_good", ExecutionStatus.CREATED))
        audit.append(_execution("good-exec", "inspect_good", ExecutionStatus.RUNNING))

        # Simulate partial/corrupt restoration of one execution's latest state.
        audit._connection.execute(
            "UPDATE execution_audit SET status = ? WHERE execution_id = ? AND status = ?",
            ("not-a-real-state", "bad-exec", "running"),
        )
        audit._connection.commit()

        recovered = audit.recover_incomplete_executions()
        assert [item.execution_id for item in recovered] == ["good-exec"]
        checker = ExecutionJournalConsistencyChecker(idem, audit)
        bad_report = checker.inspect("bad-key")
        assert bad_report.status is JournalConsistencyStatus.CONFLICT
        assert not bad_report.may_dispatch
        good_report = checker.inspect("good-key")
        assert good_report.status is JournalConsistencyStatus.RECONCILIATION_REQUIRED
        assert not good_report.may_dispatch
        assert [row["status"] for row in audit.get_history("good-exec")] == [
            "created", "running", "recovery_required"
        ]
    finally:
        idem.close()
        audit.close()


def test_recovery_only_changes_running_commands_and_preserves_terminal_history(tmp_path):
    idem, audit = _stores(tmp_path)
    try:
        idem.claim("running-key", "inspect_running", {"unit": "R"}, execution_id="running-exec")
        idem.claim("done-key", "inspect_done", {"unit": "D"}, execution_id="done-exec")
        audit.append(_execution("running-exec", "inspect_running", ExecutionStatus.CREATED))
        audit.append(_execution("running-exec", "inspect_running", ExecutionStatus.RUNNING))
        audit.append(_execution("done-exec", "inspect_done", ExecutionStatus.CREATED))
        audit.append(_execution("done-exec", "inspect_done", ExecutionStatus.RUNNING))
        audit.append(_execution("done-exec", "inspect_done", ExecutionStatus.COMPLETED))

        recovered = audit.recover_incomplete_executions()
        assert [item.execution_id for item in recovered] == ["running-exec"]
        assert [row["status"] for row in audit.get_history("done-exec")] == [
            "created", "running", "completed"
        ]
        assert audit.recover_incomplete_executions() == ()
    finally:
        idem.close()
        audit.close()
