import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_not_executed_reconciliation_requires_unknown_state_and_keeps_audit(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-232", "move", {"x": 1}, execution_id="exec-232")
        with pytest.raises(ValueError, match="only unknown outcomes"):
            store.reconcile_not_executed("key-232", evidence="external-proof", execution_id="exec-232")
        store.mark_unknown("key-232", "external response missing")
        record = store.reconcile_not_executed("key-232", evidence="external-proof", execution_id="exec-232")
        assert record.status is IdempotencyStatus.CLAIMED
        assert record.dispatch_started is False
        row = store._connection.execute("SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=?", ("key-232",)).fetchone()
        assert tuple(row) == ("external-proof", "not_executed", 0)
    finally:
        store.close()
