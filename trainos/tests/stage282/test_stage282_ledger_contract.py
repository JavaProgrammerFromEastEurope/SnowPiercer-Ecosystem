import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_unknown_outcome_requires_reconciliation_before_completion(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-282", "move", {"x": 1}, execution_id="exec-282")
        unknown = store.mark_unknown("key-282", "ack timeout")
        with pytest.raises(ValueError, match="must be reconciled"):
            store.complete("key-282", {"ok": True}, execution_id="exec-282")
        assert store.get("key-282") == unknown
        assert store.get("key-282").status is IdempotencyStatus.UNKNOWN
    finally:
        store.close()
