import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_legacy_schema_migrates_without_losing_command(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE command_idempotency (idempotency_key TEXT PRIMARY KEY, command_name TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('claimed','unknown','completed')), result_json TEXT, uncertainty_reason TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), CHECK((status='completed' AND result_json IS NOT NULL AND uncertainty_reason IS NULL) OR (status='unknown' AND result_json IS NULL AND uncertainty_reason IS NOT NULL) OR (status='claimed' AND result_json IS NULL AND uncertainty_reason IS NULL)))")
    connection.execute("INSERT INTO command_idempotency(idempotency_key, command_name, fingerprint, status) VALUES ('legacy388','charge',?, 'claimed')", ('a'*64,))
    connection.commit(); connection.close()
    store = CommandIdempotencyStore(path)
    try:
        record = store.get('legacy388')
        columns = {row['name'] for row in store._connection.execute('PRAGMA table_info(command_idempotency)')}
        indexes = {row['name'] for row in store._connection.execute('PRAGMA index_list(command_idempotency)')}
        assert record is not None and record.status.value == 'claimed'
        assert {'execution_id','dispatch_started','dispatch_generation'} <= columns
        assert 'idx_command_idempotency_execution_id' in indexes
        assert store.check_integrity() == ()
    finally: store.close()
