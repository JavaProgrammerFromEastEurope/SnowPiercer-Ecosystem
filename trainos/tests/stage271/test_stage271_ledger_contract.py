import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


@pytest.mark.parametrize("payload", [object(), {"bad": object()}])
def test_non_json_payload_is_rejected_without_creating_claim(tmp_path, payload):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="payload must be JSON-serializable"):
            store.claim("key-271", "move", payload)
        assert store.get("key-271") is None
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 0
    finally:
        store.close()
