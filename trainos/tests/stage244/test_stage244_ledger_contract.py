import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_command_cannot_be_marked_unknown(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-244", "move", {"x": 1})
        completed = store.complete("key-244", {"ok": True})
        with pytest.raises(ValueError, match="only claimed commands"):
            store.mark_unknown("key-244", "late timeout")
        assert store.get("key-244") == completed
        assert store.get("key-244").status is IdempotencyStatus.COMPLETED
    finally:
        store.close()
