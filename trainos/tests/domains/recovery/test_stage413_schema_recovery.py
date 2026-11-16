import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_structurally_incomplete_schema_is_not_stamped_current(tmp_path):
    path = tmp_path / "incomplete.sqlite3"
    c = sqlite3.connect(path); c.execute("CREATE TABLE command_idempotency (idempotency_key TEXT PRIMARY KEY)"); c.commit(); c.close()
    with pytest.raises(RuntimeError, match="missing required columns"):
        CommandIdempotencyStore(path)
    c = sqlite3.connect(path)
    try:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 0
        assert {r[1] for r in c.execute("PRAGMA table_info(command_idempotency)")} == {"idempotency_key"}
    finally: c.close()
