import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_completion_does_not_change_result_or_audit(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-306", "move", {"x": 1}, execution_id="exec-306")
        first = store.complete("key-306", {"ok": True}, execution_id="exec-306")
        with pytest.raises(IdempotencyConflict, match="conflicting duplicate"):
            store.complete("key-306", {"ok": False}, execution_id="exec-306")
        assert store.get("key-306") == first
        assert store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0] == 0
    finally:
        store.close()
