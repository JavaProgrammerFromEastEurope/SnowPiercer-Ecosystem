import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus


def test_conflicting_duplicate_completion_preserves_original_result(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-274", "move", {"x": 1}, execution_id="exec-274")
        store.complete("key-274", {"ok": True}, execution_id="exec-274")
        with pytest.raises(IdempotencyConflict, match="conflicting duplicate"):
            store.complete("key-274", {"ok": False}, execution_id="exec-274")
        record = store.get("key-274")
        assert record.status is IdempotencyStatus.COMPLETED
        assert record.result == {"ok": True}
    finally:
        store.close()
