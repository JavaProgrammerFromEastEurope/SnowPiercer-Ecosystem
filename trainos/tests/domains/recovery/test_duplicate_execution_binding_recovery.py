"""Recovery must fail closed if durable execution bindings are duplicated."""

from kernel.command.execution.command_execution import CommandExecution
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
from kernel.command.execution.execution_audit_store import ExecutionAuditStore
from kernel.command.execution.execution_journal_consistency import (
    ExecutionJournalConsistencyChecker,
    JournalConsistencyStatus,
)
from kernel.command.execution.execution_progress import ExecutionProgress
from kernel.command.execution.execution_status import ExecutionStatus


def _execution(execution_id: str, command_id: str) -> CommandExecution:
    return CommandExecution(
        execution_id=execution_id,
        command_id=command_id,
        progress=ExecutionProgress(attempts=1, max_attempts=3, completed=False),
        status=ExecutionStatus.CREATED,
    )


def test_duplicate_execution_binding_in_corrupted_ledger_blocks_both_commands(tmp_path):
    idem = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    audit = ExecutionAuditStore(tmp_path / "execution.sqlite3")
    try:
        idem.claim("key-a", "inspect_brakes", {"unit": "A"}, execution_id="shared-exec")
        idem.claim("key-b", "inspect_doors", {"unit": "B"}, execution_id="exec-b")
        audit.append(_execution("shared-exec", "inspect_brakes"))
        audit.append(_execution("exec-b", "inspect_doors"))

        # Simulate a damaged/restored ledger whose uniqueness index was lost.
        idem._connection.execute("DROP INDEX idx_command_idempotency_execution_id")
        original = idem.get("key-a")
        idem._connection.execute(
            "INSERT INTO command_idempotency "
            "(idempotency_key, command_name, fingerprint, status, execution_id) "
            "VALUES (?, ?, ?, 'claimed', ?)",
            ("key-corrupt", original.command_name, original.fingerprint, "shared-exec"),
        )
        idem._connection.commit()

        checker = ExecutionJournalConsistencyChecker(idem, audit)
        for key in ("key-a", "key-corrupt"):
            report = checker.inspect(key)
            assert report.status is JournalConsistencyStatus.CONFLICT
            assert not report.may_dispatch
            assert "multiple idempotency records" in report.reason

        # An unrelated command with a unique binding remains independently inspectable.
        independent = checker.inspect("key-b")
        assert independent.status is JournalConsistencyStatus.CONSISTENT
        assert independent.may_dispatch
        assert len(audit.get_history("shared-exec")) == 1
    finally:
        idem.close()
        audit.close()


def test_normal_api_prevents_duplicate_execution_binding_before_recovery(tmp_path):
    from kernel.command.execution.command_idempotency_store import IdempotencyConflict
    import pytest

    store = CommandIdempotencyStore(tmp_path / "idempotency.sqlite3")
    try:
        store.claim("key-a", "inspect", {"unit": "A"}, execution_id="shared-exec")
        with pytest.raises(IdempotencyConflict, match="already bound"):
            store.claim("key-b", "inspect", {"unit": "B"}, execution_id="shared-exec")
        assert store.get("key-a") is not None
        assert store.get("key-b") is None
    finally:
        store.close()
