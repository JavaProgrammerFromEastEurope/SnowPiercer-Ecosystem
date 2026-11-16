import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_future_schema_version_is_refused_without_mutation(tmp_path):
    path = tmp_path / "future.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
    connection.execute("INSERT INTO sentinel VALUES ('preserve')")
    connection.execute("PRAGMA user_version = 99")
    connection.commit(); connection.close()
    with pytest.raises(RuntimeError, match="unsupported ledger schema version 99"):
        CommandIdempotencyStore(path)
    check = sqlite3.connect(path)
    try:
        assert check.execute("PRAGMA user_version").fetchone()[0] == 99
        assert check.execute("SELECT value FROM sentinel").fetchone()[0] == "preserve"
        assert check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_idempotency'").fetchone() is None
    finally:
        check.close()
