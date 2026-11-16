import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_reserving_unknown_key_fails_without_creating_a_ledger_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="unknown idempotency key"):
            store.reserve_dispatch("missing-245")
        assert store.get("missing-245") is None
        count = store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0]
        assert count == 0
    finally:
        store.close()
