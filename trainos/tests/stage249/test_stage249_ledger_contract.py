import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_duplicate_completion_is_rejected_without_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-249", "move", {"x": 1}, execution_id="exec-249")
        original = store.complete("key-249", {"ok": True}, execution_id="exec-249")
        with pytest.raises(IdempotencyConflict, match="conflicting duplicate"):
            store.complete("key-249", {"ok": False}, execution_id="exec-249")
        assert store.get("key-249") == original
    finally:
        store.close()
