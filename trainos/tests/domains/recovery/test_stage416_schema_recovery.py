import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_future_version_still_refuses_migration_and_preserves_schema(tmp_path):
    path = tmp_path / "future.sqlite3"
    c = sqlite3.connect(path); c.execute("CREATE TABLE sentinel (v TEXT)"); c.execute("INSERT INTO sentinel VALUES ('unchanged')"); c.execute("PRAGMA user_version=7"); c.commit(); c.close()
    with pytest.raises(RuntimeError, match="maximum supported version is 1"):
        CommandIdempotencyStore(path)
    c = sqlite3.connect(path)
    try:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 7
        assert c.execute("SELECT v FROM sentinel").fetchone()[0] == "unchanged"
        assert c.execute("SELECT name FROM sqlite_master WHERE name='command_idempotency'").fetchone() is None
    finally: c.close()
