import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_non_finite_payload_is_rejected_before_any_claim_is_written(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="JSON-serializable"):
            store.claim("key-236", "move", {"x": float("nan")}, execution_id="exec-236")
        assert store.get("key-236") is None
        count = store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0]
        assert count == 0
    finally:
        store.close()
