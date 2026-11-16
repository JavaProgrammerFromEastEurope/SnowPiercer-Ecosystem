import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_completion_rejects_wrong_execution_id_without_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        before = store.claim("key-329", "charge", {"amount": 100}, execution_id="exec-329").record
        with pytest.raises(IdempotencyConflict, match="does not match"):
            store.complete("key-329", {"accepted": True}, execution_id="exec-other")
        assert store.get("key-329") == before
    finally:
        store.close()
