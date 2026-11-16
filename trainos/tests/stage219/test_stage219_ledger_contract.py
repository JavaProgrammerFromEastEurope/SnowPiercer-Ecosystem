import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_conflicting_duplicate_result_does_not_overwrite_completed_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-219", "move", {"x": 1}, execution_id="exec-219")
        original = store.complete("key-219", {"ok": True}, execution_id="exec-219")
        with pytest.raises(IdempotencyConflict):
            store.complete("key-219", {"ok": False}, execution_id="exec-219")
        current = store.get("key-219")
        assert current.status is IdempotencyStatus.COMPLETED
        assert current.result == original.result == {"ok": True}
    finally:
        store.close()
