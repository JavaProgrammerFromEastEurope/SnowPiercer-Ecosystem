import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_command_requires_reconciliation_before_completion(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-212", "move", {"x": 1}, execution_id="exec-212")
        store.mark_unknown("key-212", "ack timeout")
        before = store.get("key-212")
        with pytest.raises(ValueError, match="must be reconciled"):
            store.complete("key-212", {"ok": True}, execution_id="exec-212")
        assert store.get("key-212") == before
        assert before.status is IdempotencyStatus.UNKNOWN
    finally:
        store.close()
