import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_execution_id_is_unique_across_distinct_idempotency_keys(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-227-a", "move", {"x": 1}, execution_id="exec-227")
        with pytest.raises(IdempotencyConflict, match="already bound"):
            store.claim("key-227-b", "rotate", {"y": 2}, execution_id="exec-227")
        assert store.get("key-227-a") is not None
        assert store.get("key-227-b") is None
        assert store.count_execution_bindings("exec-227") == 1
    finally:
        store.close()
