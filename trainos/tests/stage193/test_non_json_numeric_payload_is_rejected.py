import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_non_json_numeric_payload_is_rejected(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "s.sqlite3")
    try:
        with pytest.raises(ValueError, match="JSON-serializable"):
            store.claim("key-193", "move", {"x": float("nan")}, execution_id="exec-193")
        assert store.get("key-193") is None
    finally:
        store.close()
