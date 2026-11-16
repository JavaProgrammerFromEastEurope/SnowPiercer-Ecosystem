import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_equivalent_result_object_key_order_is_idempotent(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-248", "move", {"x": 1}, execution_id="exec-248")
        first = store.complete("key-248", {"ok": True, "meta": {"a": 1, "b": 2}}, execution_id="exec-248")
        second = store.complete("key-248", {"meta": {"b": 2, "a": 1}, "ok": True}, execution_id="exec-248")
        assert second == first
        assert store.get("key-248") == first
    finally:
        store.close()
