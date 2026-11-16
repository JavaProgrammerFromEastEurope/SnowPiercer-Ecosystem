import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_claimed_command_cannot_be_reconciled_as_not_executed(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        claimed = store.claim("key-332", "charge", {"amount": 100}).record
        with pytest.raises(ValueError, match="only unknown outcomes can be reconciled"):
            store.reconcile_not_executed("key-332", evidence="provider confirms no charge")
        assert store.get("key-332") == claimed
        assert store.get("key-332").status is IdempotencyStatus.CLAIMED
        rows = store._connection.execute(
            "SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?", ("key-332",)
        ).fetchone()[0] if store._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'"
        ).fetchone() else 0
        assert rows == 0
    finally:
        store.close()
