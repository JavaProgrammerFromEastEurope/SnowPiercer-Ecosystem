import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_bound_command_completion_requires_execution_id(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        before = store.claim("key-328", "charge", {"amount": 100}, execution_id="exec-328").record
        with pytest.raises(IdempotencyConflict, match="requires matching execution_id"):
            store.complete("key-328", {"accepted": True})
        assert store.get("key-328") == before
    finally:
        store.close()
