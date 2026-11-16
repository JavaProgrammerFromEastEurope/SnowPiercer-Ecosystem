import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_same_key_different_command_is_rejected_without_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        original = store.claim("key-199", "move", {"x": 1}, execution_id="exec-199").record
        with pytest.raises(IdempotencyConflict, match="different command"):
            store.claim("key-199", "stop", {"x": 1}, execution_id="exec-199")
        assert store.get("key-199") == original
    finally:
        store.close()
