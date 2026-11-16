import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_command_requires_reconciliation_before_completion(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-262", "move", {"x": 1}, execution_id="exec-262")
        store.mark_unknown("key-262", "ack timeout")
        with pytest.raises(ValueError, match="must be reconciled"):
            store.complete("key-262", {"ok": True}, execution_id="exec-262")
        assert store.get("key-262").status is IdempotencyStatus.UNKNOWN
    finally:
        store.close()
