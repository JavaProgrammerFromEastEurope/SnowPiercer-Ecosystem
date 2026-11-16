import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_reconcile_not_executed_on_claimed_record_does_not_mutate_or_audit(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-254", "move", {"x": 1}, execution_id="exec-254")
        before = store.get("key-254")
        with pytest.raises(ValueError, match="only unknown outcomes"):
            store.reconcile_not_executed("key-254", evidence="proof-254", execution_id="exec-254")
        assert store.get("key-254") == before
        assert store._connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone()[0] == 0
        assert before.status is IdempotencyStatus.CLAIMED
    finally:
        store.close()
