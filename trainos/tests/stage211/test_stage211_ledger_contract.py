import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_duplicate_completion_does_not_overwrite_first_result(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-211", "move", {"x": 1}, execution_id="exec-211")
        first = store.complete("key-211", {"ok": True, "position": 4}, execution_id="exec-211")
        with pytest.raises(IdempotencyConflict, match="conflicting duplicate"):
            store.complete("key-211", {"ok": False}, execution_id="exec-211")
        assert store.get("key-211") == first
    finally:
        store.close()
