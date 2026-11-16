import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_execution_identity_is_unique_across_command_keys(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-200a", "move", {"x": 1}, execution_id="exec-200")
        with pytest.raises(IdempotencyConflict, match="already bound"):
            store.claim("key-200b", "move", {"x": 2}, execution_id="exec-200")
        assert store.get("key-200b") is None
        assert store.count_execution_bindings("exec-200") == 1
    finally:
        store.close()
