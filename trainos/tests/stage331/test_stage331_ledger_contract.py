import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_completed_command_cannot_be_reconciled_as_not_executed(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-331", "charge", {"amount": 100})
        completed = store.complete("key-331", {"accepted": True})
        with pytest.raises(ValueError, match="only unknown outcomes can be reconciled"):
            store.reconcile_not_executed("key-331", evidence="provider confirms no charge")
        assert store.get("key-331") == completed
        assert store.get("key-331").status is IdempotencyStatus.COMPLETED
    finally:
        store.close()
