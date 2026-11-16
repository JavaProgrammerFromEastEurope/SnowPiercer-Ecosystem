import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_corrupt_persisted_result_is_detected_on_read(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-287", "move", {"x": 1}, execution_id="exec-287")
        store.complete("key-287", {"ok": True}, execution_id="exec-287")
        with store._connection:
            store._connection.execute(
                "UPDATE command_idempotency SET result_json='{not-json' WHERE idempotency_key='key-287'"
            )
        with pytest.raises(RuntimeError, match="corrupt command idempotency record"):
            store.get("key-287")
    finally:
        store.close()
