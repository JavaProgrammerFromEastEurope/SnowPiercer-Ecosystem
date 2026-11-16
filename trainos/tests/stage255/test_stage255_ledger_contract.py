import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_sql_check_constraint_rejects_unsupported_status(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-255", "move", {"x": 1}, execution_id="exec-255")
        with pytest.raises(sqlite3.IntegrityError):
            store._connection.execute("UPDATE command_idempotency SET status='pending' WHERE idempotency_key=?", ("key-255",))
        store._connection.rollback()
        assert store.get("key-255").status.value == "claimed"
    finally:
        store.close()
