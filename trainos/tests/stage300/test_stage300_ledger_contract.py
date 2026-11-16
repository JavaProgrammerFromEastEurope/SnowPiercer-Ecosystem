import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_command_cannot_transition_back_to_unknown(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-300", "move", {"x": 1}, execution_id="exec-300")
        completed = store.complete("key-300", {"ok": True}, execution_id="exec-300")
        with pytest.raises(ValueError, match="only claimed commands can become unknown"):
            store.mark_unknown("key-300", "late timeout")
        assert store.get("key-300") == completed
        assert store.get("key-300").status is IdempotencyStatus.COMPLETED
    finally:
        store.close()
