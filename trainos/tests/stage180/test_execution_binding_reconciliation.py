import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_wrong_execution_identity_cannot_reconcile_unknown_outcome(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "binding.sqlite3")
    try:
        store.claim("key-180", "inspect", {"target": "A"}, execution_id="exec-180")
        store.reserve_dispatch("key-180")
        store.mark_unknown("key-180", "lost ack")
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.reconcile_not_executed("key-180", evidence="no-execution receipt", execution_id="wrong-exec")
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.reconcile_completed("key-180", {"ok": True}, evidence="completion receipt", execution_id="wrong-exec")
        record = store.get("key-180")
        assert record.status.value == "unknown"
        assert record.dispatch_started is True
        assert store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0] == 0
    finally:
        store.close()
