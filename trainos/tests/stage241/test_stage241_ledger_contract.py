import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_execution_binding_count_tracks_distinct_bound_commands(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-241-a", "move", {"x": 1}, execution_id="exec-241-a")
        store.claim("key-241-b", "rotate", {"y": 2}, execution_id="exec-241-b")
        store.claim("key-241-c", "wait", {"ticks": 1})
        assert store.count_execution_bindings("exec-241-a") == 1
        assert store.count_execution_bindings("exec-241-b") == 1
        assert store.count_execution_bindings("exec-241-c") == 0
    finally:
        store.close()
