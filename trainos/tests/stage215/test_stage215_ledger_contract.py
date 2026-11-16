import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_nonfinite_payload_rejected_without_record_creation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="JSON-serializable"):
            store.claim("key-215", "move", {"x": float("nan")}, execution_id="exec-215")
        assert store.get("key-215") is None
    finally:
        store.close()
