import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_equivalent_payload_key_order_reuses_existing_claim(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-258", "move", {"x": 1, "meta": {"a": 2, "b": 3}}, execution_id="exec-258")
        second = store.claim("key-258", "move", {"meta": {"b": 3, "a": 2}, "x": 1}, execution_id="exec-258")
        assert first.created is True
        assert second.created is False
        assert second.record == first.record
    finally:
        store.close()
