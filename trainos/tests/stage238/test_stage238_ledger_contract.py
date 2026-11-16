import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_claim_fingerprint_is_independent_of_mapping_insertion_order(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-238", "move", {"x": 1, "y": 2}, execution_id="exec-238")
        second = store.claim("key-238", "move", {"y": 2, "x": 1}, execution_id="exec-238")
        assert first.created is True
        assert second.created is False
        assert second.record == first.record
    finally:
        store.close()
