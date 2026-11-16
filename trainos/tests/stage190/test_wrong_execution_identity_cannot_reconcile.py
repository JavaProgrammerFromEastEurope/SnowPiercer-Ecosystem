import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_wrong_execution_identity_cannot_reconcile(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "s.sqlite3")
    try:
        store.claim("key-190", "move", {"x": 1}, execution_id="exec-190")
        store.mark_unknown("key-190", "ack timeout")
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.reconcile_completed("key-190", {"ok": True}, evidence="external receipt", execution_id="other-exec")
        assert store.get("key-190").status.value == "unknown"
    finally:
        store.close()
