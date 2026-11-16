import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_blank_evidence_rejected_without_mutating_unknown_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-208", "move", {"x": 1}, execution_id="exec-208")
        store.mark_unknown("key-208", "ack timeout")
        before = store.get("key-208")
        with pytest.raises(ValueError, match="evidence must not be empty"):
            store.reconcile_completed("key-208", {"ok": True}, evidence="   ", execution_id="exec-208")
        assert store.get("key-208") == before
        assert store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0] == 0
    finally:
        store.close()
