import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

@pytest.mark.parametrize("evidence", ["", "   "])
def test_blank_reconciliation_evidence_does_not_change_unknown_state(tmp_path, evidence):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-294", "move", {"x": 1}, execution_id="exec-294")
        store.mark_unknown("key-294", "ack timeout")
        before = store.get("key-294")
        with pytest.raises(ValueError, match="evidence must not be empty"):
            store.reconcile_completed("key-294", {"ok": True}, evidence=evidence, execution_id="exec-294")
        assert store.get("key-294") == before
        assert before.status is IdempotencyStatus.UNKNOWN
        assert store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0] == 0
    finally:
        store.close()
