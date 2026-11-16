import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_restored_legacy_database_is_migrated_and_reopen_is_stable(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE command_idempotency (idempotency_key TEXT PRIMARY KEY, command_name TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('claimed','unknown','completed')), result_json TEXT, uncertainty_reason TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), CHECK((status='completed' AND result_json IS NOT NULL AND uncertainty_reason IS NULL) OR (status='unknown' AND result_json IS NULL AND uncertainty_reason IS NOT NULL) OR (status='claimed' AND result_json IS NULL AND uncertainty_reason IS NULL)))")
    c.execute("INSERT INTO command_idempotency(idempotency_key,command_name,fingerprint,status) VALUES ('legacy404','charge',?,'claimed')", ('c'*64,))
    c.commit(); c.close()
    first = CommandIdempotencyStore(path)
    try:
        assert first.get("legacy404").status.value == "claimed"
        assert first._connection.execute("PRAGMA user_version").fetchone()[0] == 1
    finally: first.close()
    second = CommandIdempotencyStore(path)
    try:
        assert second.get("legacy404").status.value == "claimed"
        assert second.check_integrity() == ()
    finally: second.close()
