import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_bound_command_requires_matching_execution_id_for_completion(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-315", "move", {"x": 1}, execution_id="exec-315")
        before = store.get("key-315")
        with pytest.raises(IdempotencyConflict, match="requires matching execution_id"):
            store.complete("key-315", {"ok": True})
        assert store.get("key-315") == before
    finally:
        store.close()
