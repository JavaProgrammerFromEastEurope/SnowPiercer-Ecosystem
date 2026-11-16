import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_repeated_claim_rejects_conflicting_execution_binding(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        original = store.claim("key-334", "charge", {"amount": 100}, execution_id="exec-334").record
        with pytest.raises(IdempotencyConflict, match="different execution"):
            store.claim("key-334", "charge", {"amount": 100}, execution_id="exec-other")
        assert store.get("key-334") == original
        assert store.count_execution_bindings("exec-334") == 1
        assert store.count_execution_bindings("exec-other") == 0
    finally:
        store.close()
