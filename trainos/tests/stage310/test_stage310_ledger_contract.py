import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_execution_id_cannot_be_attached_after_claim(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-310", "move", {"x": 1}).record
        with pytest.raises(IdempotencyConflict, match="cannot bind execution_id after command claim"):
            store.claim("key-310", "move", {"x": 1}, execution_id="exec-310")
        assert store.get("key-310") == first
    finally:
        store.close()
