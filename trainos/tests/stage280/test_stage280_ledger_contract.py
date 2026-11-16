import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict


def test_execution_id_uniqueness_holds_across_store_instances(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    first = CommandIdempotencyStore(path)
    second = CommandIdempotencyStore(path)
    try:
        first.claim("key-280-a", "move", {"x": 1}, execution_id="exec-280")
        with pytest.raises(IdempotencyConflict, match="already bound"):
            second.claim("key-280-b", "move", {"x": 2}, execution_id="exec-280")
        assert first.count_execution_bindings("exec-280") == 1
        assert second.get("key-280-b") is None
    finally:
        first.close()
        second.close()
