import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_blank_reconciliation_evidence_is_rejected_without_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-264", "move", {"x": 1}, execution_id="exec-264")
        store.mark_unknown("key-264", "ack timeout")
        before = store.get("key-264")
        with pytest.raises(ValueError, match="evidence must not be empty"):
            store.reconcile_completed("key-264", {"ok": True}, evidence="  ", execution_id="exec-264")
        assert store.get("key-264") == before
        assert store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0] == 0
    finally:
        store.close()
