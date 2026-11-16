import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_migration_can_retry_after_duplicate_binding_is_corrected(tmp_path):
    path = tmp_path / "retry.sqlite3"
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE command_idempotency (idempotency_key TEXT PRIMARY KEY, command_name TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT, uncertainty_reason TEXT, created_at TEXT NOT NULL DEFAULT 'now', updated_at TEXT NOT NULL DEFAULT 'now', execution_id TEXT)")
    c.executemany("INSERT INTO command_idempotency(idempotency_key,command_name,fingerprint,status,execution_id) VALUES(?,?,?,'claimed',?)", [("a","cmd","a"*64,"same"),("b","cmd","b"*64,"same")])
    c.commit(); c.close()
    with pytest.raises(sqlite3.IntegrityError): CommandIdempotencyStore(path)
    c = sqlite3.connect(path); c.execute("UPDATE command_idempotency SET execution_id=NULL WHERE idempotency_key='b'"); c.commit(); c.close()
    store = CommandIdempotencyStore(path)
    try:
        assert store._connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert store.get("a").execution_id == "same"
        assert store.get("b").execution_id is None
        assert store.check_integrity() == ()
    finally: store.close()
