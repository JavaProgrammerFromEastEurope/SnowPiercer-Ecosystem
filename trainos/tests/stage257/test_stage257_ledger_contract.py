import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_duplicate_execution_id_claim_does_not_create_second_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-257-a", "move", {"x": 1}, execution_id="exec-257")
        with pytest.raises(IdempotencyConflict, match="already bound"):
            store.claim("key-257-b", "rotate", {"y": 2}, execution_id="exec-257")
        assert store.get("key-257-a") is not None
        assert store.get("key-257-b") is None
        assert store.count_execution_bindings("exec-257") == 1
    finally:
        store.close()
