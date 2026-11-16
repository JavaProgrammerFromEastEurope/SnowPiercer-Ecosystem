import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_missing_key_reconciliation_fails_without_creating_ledger_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="unknown idempotency key"):
            store.reconcile_not_executed("missing-226", evidence="proof-226")
        assert store.get("missing-226") is None
        count = store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0]
        assert count == 0
    finally:
        store.close()
