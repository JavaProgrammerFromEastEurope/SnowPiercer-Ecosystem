import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_integrity_check_detects_non_unique_execution_index(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        store._connection.execute("DROP INDEX idx_command_idempotency_execution_id")
        store._connection.execute("CREATE INDEX idx_command_idempotency_execution_id ON command_idempotency(execution_id) WHERE execution_id IS NOT NULL")
        store._connection.commit()
        findings = store.check_integrity()
        assert "schema: execution_id index is not unique" in findings
    finally: store.close()
