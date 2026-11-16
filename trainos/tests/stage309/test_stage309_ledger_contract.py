import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_reusing_key_for_different_command_name_is_rejected_without_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-309", "move", {"x": 1}, execution_id="exec-309").record
        with pytest.raises(IdempotencyConflict, match="different command"):
            store.claim("key-309", "stop", {"x": 1}, execution_id="exec-309")
        assert store.get("key-309") == first
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        store.close()
