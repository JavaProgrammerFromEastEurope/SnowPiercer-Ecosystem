import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_command_rejects_not_executed_reconciliation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-213", "move", {"x": 1}, execution_id="exec-213")
        completed = store.complete("key-213", {"ok": True}, execution_id="exec-213")
        with pytest.raises(ValueError, match="only unknown outcomes"):
            store.reconcile_not_executed("key-213", evidence="proof-213", execution_id="exec-213")
        assert store.get("key-213") == completed
    finally:
        store.close()
