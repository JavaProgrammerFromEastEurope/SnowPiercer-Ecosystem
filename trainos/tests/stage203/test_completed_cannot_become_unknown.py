import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_command_cannot_be_marked_unknown(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-203", "move", {"x": 1}, execution_id="exec-203")
        store.complete("key-203", {"ok": True}, execution_id="exec-203")
        with pytest.raises(ValueError, match="only claimed commands"):
            store.mark_unknown("key-203", "late timeout")
        record = store.get("key-203")
        assert record.status is IdempotencyStatus.COMPLETED
        assert record.result == {"ok": True}
    finally:
        store.close()
