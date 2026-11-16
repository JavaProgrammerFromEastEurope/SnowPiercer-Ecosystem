import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


@pytest.mark.parametrize("evidence", ["", "   ", "\t\n"])
def test_blank_reconciliation_evidence_is_rejected_atomically(tmp_path, evidence):
    store = CommandIdempotencyStore(tmp_path / "blank-evidence.sqlite3")
    try:
        store.claim("key-181", "inspect", {"target": "B"}, execution_id="exec-181")
        store.reserve_dispatch("key-181")
        store.mark_unknown("key-181", "lost ack")
        with pytest.raises(ValueError, match="evidence must not be empty"):
            store.reconcile_completed("key-181", {"ok": True}, evidence=evidence, execution_id="exec-181")
        record = store.get("key-181")
        assert record.status.value == "unknown"
        assert record.dispatch_started is True
        assert store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0] == 0
    finally:
        store.close()
