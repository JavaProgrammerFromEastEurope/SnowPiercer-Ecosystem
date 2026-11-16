import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_missing_key_cannot_reserve_dispatch_or_create_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="unknown idempotency key"):
            store.reserve_dispatch("missing-265")
        assert store.get("missing-265") is None
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 0
    finally:
        store.close()
