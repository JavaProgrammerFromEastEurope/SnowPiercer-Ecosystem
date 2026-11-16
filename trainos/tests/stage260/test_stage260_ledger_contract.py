import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_blank_execution_id_does_not_create_claim(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="execution_id must not be empty"):
            store.claim("key-260", "move", {"x": 1}, execution_id="   ")
        assert store.get("key-260") is None
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 0
    finally:
        store.close()
