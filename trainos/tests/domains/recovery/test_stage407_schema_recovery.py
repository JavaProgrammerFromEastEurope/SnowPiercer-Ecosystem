import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_unsupported_schema_is_rejected_before_ledger_table_creation(tmp_path):
    path = tmp_path / "unsupported.sqlite3"
    c = sqlite3.connect(path); c.execute("PRAGMA user_version=2"); c.commit(); c.close()
    with pytest.raises(RuntimeError, match="maximum supported version is 1"):
        CommandIdempotencyStore(path)
    c = sqlite3.connect(path)
    try:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 2
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_idempotency'").fetchone() is None
    finally: c.close()
