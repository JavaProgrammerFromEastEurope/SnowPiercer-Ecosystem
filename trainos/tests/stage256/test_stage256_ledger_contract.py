import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_corrupt_fingerprint_is_detected_when_record_is_read(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-256", "move", {"x": 1}, execution_id="exec-256")
        store._connection.execute("UPDATE command_idempotency SET fingerprint='broken' WHERE idempotency_key=?", ("key-256",))
        store._connection.commit()
        with pytest.raises(RuntimeError, match="corrupt command idempotency fingerprint"):
            store.get("key-256")
    finally:
        store.close()
