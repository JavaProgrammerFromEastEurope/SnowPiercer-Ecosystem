import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_completion_requires_matching_execution_identity(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-298", "move", {"x": 1}, execution_id="exec-298")
        before = store.get("key-298")
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.complete("key-298", {"ok": True}, execution_id="exec-other-298")
        assert store.get("key-298") == before
    finally:
        store.close()
