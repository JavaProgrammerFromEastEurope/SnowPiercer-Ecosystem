import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_cannot_be_completed_without_reconciliation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-221", "move", {"x": 1}, execution_id="exec-221")
        store.mark_unknown("key-221", "ack timeout")
        with pytest.raises(ValueError, match="must be reconciled"):
            store.complete("key-221", {"ok": True}, execution_id="exec-221")
        record = store.get("key-221")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.result is None
    finally:
        store.close()
