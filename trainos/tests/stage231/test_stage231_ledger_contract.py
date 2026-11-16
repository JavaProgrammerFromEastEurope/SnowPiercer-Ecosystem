import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_blank_reconciliation_evidence_is_rejected_without_state_change(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-231", "move", {"x": 1}, execution_id="exec-231")
        store.mark_unknown("key-231", "lost acknowledgement")
        with pytest.raises(ValueError, match="evidence must not be empty"):
            store.reconcile_completed("key-231", {"ok": True}, evidence="  ", execution_id="exec-231")
        record = store.get("key-231")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.result is None
        count = store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0]
        assert count == 0
    finally:
        store.close()
