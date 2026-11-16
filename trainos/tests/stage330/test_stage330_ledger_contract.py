import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_completed_command_cannot_be_marked_unknown(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-330", "charge", {"amount": 100})
        completed = store.complete("key-330", {"accepted": True})
        with pytest.raises(ValueError, match="only claimed commands can become unknown"):
            store.mark_unknown("key-330", "late timeout")
        assert store.get("key-330") == completed
        assert store.get("key-330").status is IdempotencyStatus.COMPLETED
    finally:
        store.close()
