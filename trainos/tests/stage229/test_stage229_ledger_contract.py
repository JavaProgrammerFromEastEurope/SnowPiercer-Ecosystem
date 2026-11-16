import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_completed_result_is_idempotent_but_conflicting_result_is_rejected(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-229", "move", {"x": 1})
        completed = store.complete("key-229", {"ok": True, "count": 1})
        assert completed.status is IdempotencyStatus.COMPLETED
        assert store.complete("key-229", {"count": 1, "ok": True}) == completed
        with pytest.raises(IdempotencyConflict, match="conflicting duplicate"):
            store.complete("key-229", {"ok": False})
        assert store.get("key-229") == completed
    finally:
        store.close()
