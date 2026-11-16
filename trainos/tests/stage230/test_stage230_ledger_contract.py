import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_command_cannot_be_completed_without_reconciliation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-230", "move", {"x": 1})
        store.mark_unknown("key-230", "acknowledgement timeout")
        with pytest.raises(ValueError, match="must be reconciled"):
            store.complete("key-230", {"ok": True})
        record = store.get("key-230")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.result is None
        assert record.uncertainty_reason == "acknowledgement timeout"
    finally:
        store.close()
