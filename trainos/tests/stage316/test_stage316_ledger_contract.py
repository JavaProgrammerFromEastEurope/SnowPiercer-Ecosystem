import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_claimed_command_cannot_be_reconciled_as_completed(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-316", "move", {"x": 1}, execution_id="exec-316").record
        with pytest.raises(ValueError, match="only unknown outcomes can be reconciled"):
            store.reconcile_completed("key-316", {"ok": True}, evidence="receipt", execution_id="exec-316")
        assert store.get("key-316") == first
        assert store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0] == 0
        assert store.get("key-316").status is IdempotencyStatus.CLAIMED
    finally:
        store.close()
