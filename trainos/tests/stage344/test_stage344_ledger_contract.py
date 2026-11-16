import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_reconcile_completed_requires_matching_execution_id(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-344", "charge", {"amount": 344}, execution_id="exec-344")
        store.mark_unknown("key-344", "provider timeout")
        before = store.get("key-344")
        with pytest.raises(IdempotencyConflict):
            store.reconcile_completed("key-344", {"accepted": True}, evidence="provider receipt")
        assert store.get("key-344") == before
    finally:
        store.close()
