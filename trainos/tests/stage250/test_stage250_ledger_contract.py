import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_reconcile_completed_rejects_missing_or_wrong_execution_id(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-250", "move", {"x": 1}, execution_id="exec-250")
        store.reserve_dispatch("key-250")
        store.mark_unknown("key-250", "ack timeout")
        with pytest.raises(IdempotencyConflict, match="requires matching execution_id"):
            store.reconcile_completed("key-250", {"ok": True}, evidence="external-250")
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.reconcile_completed("key-250", {"ok": True}, evidence="external-250", execution_id="wrong-250")
        assert store.get("key-250").status is IdempotencyStatus.UNKNOWN
        assert store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0] == 0
    finally:
        store.close()
