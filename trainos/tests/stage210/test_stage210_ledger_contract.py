import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_completion_requires_matching_execution_identity(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        original = store.claim("key-210", "move", {"x": 1}, execution_id="exec-210").record
        with pytest.raises(IdempotencyConflict, match="requires matching execution_id"):
            store.complete("key-210", {"ok": True})
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.complete("key-210", {"ok": True}, execution_id="exec-other")
        assert store.get("key-210") == original
    finally:
        store.close()
