import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_bound_record_requires_execution_id_for_reconciliation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-222", "move", {"x": 1}, execution_id="exec-222")
        store.mark_unknown("key-222", "ack timeout")
        with pytest.raises(IdempotencyConflict, match="requires matching execution_id"):
            store.reconcile_completed("key-222", {"ok": True}, evidence="proof-222")
        assert store.get("key-222").uncertainty_reason == "ack timeout"
    finally:
        store.close()
