import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_invalid_completion_result_is_rejected_before_state_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        claimed = store.claim("key-281", "move", {"x": 1}, execution_id="exec-281").record
        with pytest.raises(ValueError, match="result must be JSON-serializable"):
            store.complete("key-281", {"bad": object()}, execution_id="exec-281")
        assert store.get("key-281") == claimed
        assert store.get("key-281").status is IdempotencyStatus.CLAIMED
    finally:
        store.close()
