import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_execution_identity_does_not_mutate_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        original = store.claim("key-289", "move", {"x": 1}, execution_id="exec-289")
        before = store.get("key-289")
        with pytest.raises(IdempotencyConflict, match="different execution"):
            store.claim("key-289", "move", {"x": 1}, execution_id="exec-other-289")
        assert store.get("key-289") == before
        assert original.created is True
    finally:
        store.close()
