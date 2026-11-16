import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_execution_id_unique_across_independent_store_instances(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    first = CommandIdempotencyStore(path)
    second = CommandIdempotencyStore(path)
    try:
        first.claim("key-290-a", "move", {"x": 1}, execution_id="exec-shared-290")
        with pytest.raises(IdempotencyConflict, match="already bound"):
            second.claim("key-290-b", "stop", {"x": 2}, execution_id="exec-shared-290")
        assert first.count_execution_bindings("exec-shared-290") == 1
        assert second.get("key-290-b") is None
    finally:
        first.close()
        second.close()
