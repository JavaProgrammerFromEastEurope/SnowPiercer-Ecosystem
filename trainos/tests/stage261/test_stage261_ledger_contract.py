import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict, IdempotencyStatus

def test_wrong_execution_id_cannot_complete_claim(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-261", "move", {"x": 1}, execution_id="exec-261")
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.complete("key-261", {"ok": True}, execution_id="other-261")
        assert store.get("key-261").status is IdempotencyStatus.CLAIMED
        assert store.get("key-261").result is None
    finally:
        store.close()
