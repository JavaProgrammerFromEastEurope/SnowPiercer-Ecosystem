import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_existing_unbound_key_cannot_be_bound_later_to_execution_id(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        original = store.claim("key-240", "move", {"x": 1}).record
        with pytest.raises(IdempotencyConflict, match="cannot bind execution_id"):
            store.claim("key-240", "move", {"x": 1}, execution_id="exec-240")
        assert store.get("key-240") == original
        assert store.count_execution_bindings("exec-240") == 0
    finally:
        store.close()
