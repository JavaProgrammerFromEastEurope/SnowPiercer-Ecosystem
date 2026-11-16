import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_nan_payload_is_rejected_before_ledger_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="payload must be JSON-serializable"):
            store.claim("key-336", "charge", {"amount": float("nan")})
        assert store.get("key-336") is None
        count = store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0]
        assert count == 0
    finally:
        store.close()
