import math
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

@pytest.mark.parametrize("payload", [object(), {"value": float("nan")}, {"value": float("inf")}])
def test_invalid_payload_is_rejected_without_insert(tmp_path, payload):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="JSON-serializable"):
            store.claim("key-291", "move", payload, execution_id="exec-291")
        assert store.get("key-291") is None
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 0
    finally:
        store.close()
