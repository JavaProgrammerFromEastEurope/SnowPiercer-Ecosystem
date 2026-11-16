import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_completed_command_cannot_be_marked_unknown(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-275", "move", {"x": 1}, execution_id="exec-275")
        store.complete("key-275", {"ok": True}, execution_id="exec-275")
        before = store.get("key-275")
        with pytest.raises(ValueError, match="only claimed commands can become unknown"):
            store.mark_unknown("key-275", "late timeout")
        assert store.get("key-275") == before
        assert store.get("key-275").status is IdempotencyStatus.COMPLETED
    finally:
        store.close()
