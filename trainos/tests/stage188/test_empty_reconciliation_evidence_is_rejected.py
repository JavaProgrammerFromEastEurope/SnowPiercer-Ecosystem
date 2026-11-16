import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_empty_reconciliation_evidence_is_rejected(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "s.sqlite3")
    try:
        store.claim("key-188", "move", {"x": 1}, execution_id="exec-188")
        store.reserve_dispatch("key-188")
        store.mark_unknown("key-188", "ack timeout")
        with pytest.raises(ValueError, match="evidence must not be empty"):
            store.reconcile_completed("key-188", {"ok": True}, evidence="   ", execution_id="exec-188")
        assert store.get("key-188").status.value == "unknown"
    finally:
        store.close()
