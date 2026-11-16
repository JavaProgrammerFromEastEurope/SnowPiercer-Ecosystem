"""Recovery must fail closed on partial/corrupt rows without blocking peers."""
import sqlite3

from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_progress import ExecutionProgress
from kernel.command.execution.execution_status import ExecutionStatus


def execution(execution_id, command_id, status):
    return CommandExecution(
        execution_id=execution_id,
        command_id=command_id,
        progress=ExecutionProgress(attempts=1, max_attempts=3, completed=False),
        status=status,
    )


def test_invalid_partial_progress_is_skipped_and_independent_execution_recovers(tmp_path):
    store = ExecutionAuditStore(tmp_path / "audit.sqlite3")
    try:
        for execution_id, command_id in (("broken", "cmd-broken"), ("healthy", "cmd-healthy")):
            store.append(execution(execution_id, command_id, ExecutionStatus.CREATED))
            store.append(execution(execution_id, command_id, ExecutionStatus.RUNNING))
        store._connection.execute(
            "UPDATE execution_audit SET attempts = 9 WHERE execution_id = ? AND status = ?",
            ("broken", "running"),
        )
        store._connection.commit()

        recovered = store.recover_incomplete_executions()

        assert [item.execution_id for item in recovered] == ["healthy"]
        assert store.get_latest_status("broken") == "running"
        assert store.get_latest_status("healthy") == "recovery_required"
        findings = store.verify_integrity()
        assert any(item["execution_id"] == "broken" and item["code"] == "invalid_progress" for item in findings)
    finally:
        store.close()


def test_uncommitted_partial_transition_disappears_after_rollback_and_reopen(tmp_path):
    path = tmp_path / "audit.sqlite3"
    store = ExecutionAuditStore(path)
    try:
        store.append(execution("stable", "cmd-stable", ExecutionStatus.CREATED))
        store._connection.execute("BEGIN")
        store._connection.execute(
            "INSERT INTO execution_audit (execution_id, command_id, status, attempts, max_attempts, completed) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("half-written", "cmd-half", "running", 1, 3, 0),
        )
        store._connection.rollback()
        assert store.get_history("half-written") == ()
    finally:
        store.close()

    reopened = ExecutionAuditStore(path)
    try:
        assert reopened.get_history("half-written") == ()
        assert reopened.recover_incomplete_executions() == ()
        assert reopened.get_latest_status("stable") == "created"
    finally:
        reopened.close()


def test_integrity_report_identifies_unknown_status_without_dispatch_repair(tmp_path):
    path = tmp_path / "audit.sqlite3"
    store = ExecutionAuditStore(path)
    try:
        store.append(execution("damaged", "cmd-damaged", ExecutionStatus.CREATED))
        store._connection.execute(
            "UPDATE execution_audit SET status = ? WHERE execution_id = ?",
            ("partial_transition", "damaged"),
        )
        store._connection.commit()
        findings = store.verify_integrity()
        assert any(item["code"] == "unknown_status" for item in findings)
        assert store.recover_incomplete_executions() == ()
        assert store.get_latest_status("damaged") == "partial_transition"
    finally:
        store.close()
