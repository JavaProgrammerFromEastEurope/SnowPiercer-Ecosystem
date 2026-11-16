import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def _legacy_with_duplicate_execution_ids(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE command_idempotency (idempotency_key TEXT PRIMARY KEY, command_name TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT, uncertainty_reason TEXT, created_at TEXT NOT NULL DEFAULT 'now', updated_at TEXT NOT NULL DEFAULT 'now', execution_id TEXT)")
    c.executemany("INSERT INTO command_idempotency(idempotency_key,command_name,fingerprint,status,execution_id) VALUES(?,?,?,'claimed',?)", [("a","cmd","a"*64,"same"),("b","cmd","b"*64,"same")])
    c.commit(); c.close()

def test_failed_index_migration_rolls_back_added_columns(tmp_path):
    path = tmp_path / "broken-legacy.sqlite3"
    _legacy_with_duplicate_execution_ids(path)
    before = sqlite3.connect(path)
    original = {r[1] for r in before.execute("PRAGMA table_info(command_idempotency)")}
    before.close()
    with pytest.raises(sqlite3.IntegrityError):
        CommandIdempotencyStore(path)
    check = sqlite3.connect(path)
    try:
        after = {r[1] for r in check.execute("PRAGMA table_info(command_idempotency)")}
        assert after == original
        assert check.execute("PRAGMA user_version").fetchone()[0] == 0
    finally: check.close()
