import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_duplicate_execution_id_is_rejected_without_second_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-333-a", "charge", {"amount": 100}, execution_id="exec-333")
        with pytest.raises(IdempotencyConflict, match="already bound"):
            store.claim("key-333-b", "refund", {"amount": 100}, execution_id="exec-333")
        assert store.get("key-333-a") is not None
        assert store.get("key-333-b") is None
        assert store.count_execution_bindings("exec-333") == 1
    finally:
        store.close()
