import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_integrity_diagnostic_reports_removed_execution_index(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "missing-index.sqlite3")
    try:
        store._connection.execute("DROP INDEX idx_command_idempotency_execution_id")
        store._connection.commit()
        assert "schema: execution_id uniqueness index is missing" in store.check_integrity()
    finally: store.close()
