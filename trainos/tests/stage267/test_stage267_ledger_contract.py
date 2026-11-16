import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_legacy_schema_migration_backfills_dispatch_generation(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("""CREATE TABLE command_idempotency (
        idempotency_key TEXT PRIMARY KEY, command_name TEXT NOT NULL, fingerprint TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('claimed', 'unknown', 'completed')),
        result_json TEXT, uncertainty_reason TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        execution_id TEXT, dispatch_started INTEGER NOT NULL DEFAULT 0 CHECK(dispatch_started IN (0,1)),
        CHECK((status='completed' AND result_json IS NOT NULL AND uncertainty_reason IS NULL)
           OR (status='unknown' AND result_json IS NULL AND uncertainty_reason IS NOT NULL)
           OR (status='claimed' AND result_json IS NULL AND uncertainty_reason IS NULL)))""")
    connection.execute("INSERT INTO command_idempotency(idempotency_key, command_name, fingerprint, status, execution_id, dispatch_started) VALUES (?, ?, ?, 'claimed', ?, 1)", ("key-267", "move", "a"*64, "exec-267"))
    connection.commit()
    connection.close()
    store = CommandIdempotencyStore(path)
    try:
        record = store.get("key-267")
        assert record is not None
        assert record.dispatch_started is True
        assert record.dispatch_generation == 1
    finally:
        store.close()
