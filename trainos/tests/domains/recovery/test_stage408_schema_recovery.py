import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_negative_schema_version_is_rejected_without_mutation(tmp_path):
    path = tmp_path / "negative.sqlite3"
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE sentinel (value TEXT)")
    c.execute("INSERT INTO sentinel VALUES ('keep')")
    c.execute("PRAGMA user_version = -1")
    c.commit(); c.close()
    with pytest.raises(RuntimeError, match="cannot be negative"):
        CommandIdempotencyStore(path)
    c = sqlite3.connect(path)
    try:
        assert c.execute("PRAGMA user_version").fetchone()[0] == -1
        assert c.execute("SELECT value FROM sentinel").fetchone()[0] == "keep"
        assert c.execute("SELECT name FROM sqlite_master WHERE name='command_idempotency'").fetchone() is None
    finally: c.close()
