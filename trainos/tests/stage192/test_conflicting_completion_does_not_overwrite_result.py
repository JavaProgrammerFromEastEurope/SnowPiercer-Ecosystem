import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_completion_does_not_overwrite_result(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "s.sqlite3")
    try:
        store.claim("key-192", "move", {"x": 1}, execution_id="exec-192")
        store.complete("key-192", {"ok": True}, execution_id="exec-192")
        with pytest.raises(IdempotencyConflict, match="conflicting duplicate"):
            store.complete("key-192", {"ok": False}, execution_id="exec-192")
        assert store.get("key-192").result == {"ok": True}
    finally:
        store.close()
