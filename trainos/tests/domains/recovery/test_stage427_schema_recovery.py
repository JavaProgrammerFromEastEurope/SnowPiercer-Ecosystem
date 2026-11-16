import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_is_valid_sqlite_snapshot_with_schema_marker(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    store.claim("final-check", "reconcile", {"release": 51})
    try:
        store.backup_to(backup)
    finally: store.close()
    db = sqlite3.connect(backup)
    try:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT idempotency_key FROM command_idempotency").fetchone()[0] == "final-check"
    finally: db.close()
