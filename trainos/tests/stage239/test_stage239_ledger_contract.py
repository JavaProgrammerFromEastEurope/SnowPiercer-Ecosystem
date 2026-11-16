import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_reusing_key_for_different_command_name_is_rejected_without_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        original = store.claim("key-239", "move", {"x": 1}, execution_id="exec-239").record
        with pytest.raises(IdempotencyConflict, match="different command"):
            store.claim("key-239", "rotate", {"x": 1}, execution_id="exec-239")
        assert store.get("key-239") == original
        assert store.count_execution_bindings("exec-239") == 1
    finally:
        store.close()
