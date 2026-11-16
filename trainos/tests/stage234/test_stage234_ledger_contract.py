import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_bound_execution_id_is_required_for_completion_and_must_match(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-234", "move", {"x": 1}, execution_id="exec-234")
        with pytest.raises(IdempotencyConflict, match="requires matching execution_id"):
            store.complete("key-234", {"ok": True})
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.complete("key-234", {"ok": True}, execution_id="other-exec")
        assert store.get("key-234").status is IdempotencyStatus.CLAIMED
        completed = store.complete("key-234", {"ok": True}, execution_id="exec-234")
        assert completed.status is IdempotencyStatus.COMPLETED
    finally:
        store.close()
