import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_execution_identity_required_for_bound_completion(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "s.sqlite3")
    try:
        store.claim("key-189", "move", {"x": 1}, execution_id="exec-189")
        with pytest.raises(IdempotencyConflict, match="requires matching execution_id"):
            store.complete("key-189", {"ok": True})
        assert store.get("key-189").status.value == "claimed"
    finally:
        store.close()
