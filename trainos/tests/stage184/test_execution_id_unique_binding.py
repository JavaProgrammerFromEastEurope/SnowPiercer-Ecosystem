import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_execution_identity_cannot_be_reused_for_another_key(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "unique-execution.sqlite3")
    try:
        store.claim("key-184-a", "move", {"x": 1}, execution_id="exec-shared-184")
        with pytest.raises(IdempotencyConflict, match="already bound"):
            store.claim("key-184-b", "move", {"x": 2}, execution_id="exec-shared-184")
        assert store.get("key-184-a") is not None
        assert store.get("key-184-b") is None
        assert store.count_execution_bindings("exec-shared-184") == 1
    finally:
        store.close()
