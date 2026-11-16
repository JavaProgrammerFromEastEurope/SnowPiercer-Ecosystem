import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_completed_reconciliation_audit_binds_current_generation(tmp_path):
    path = tmp_path / "completed-generation.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        store.claim("key-178", "set_route", {"route": "R-178"}, execution_id="exec-178")
        assert store.reserve_dispatch("key-178") is True
        store.mark_unknown("key-178", "acknowledgement missing")
        completed = store.reconcile_completed(
            "key-178", {"accepted": True}, evidence="controller completion receipt generation 1",
            execution_id="exec-178",
        )
        assert completed.status is IdempotencyStatus.COMPLETED
        row = store._connection.execute(
            "SELECT decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=?",
            ("key-178",),
        ).fetchone()
        assert tuple(row) == ("completed", 1)
    finally:
        store.close()
