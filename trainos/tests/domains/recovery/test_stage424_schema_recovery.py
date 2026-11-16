import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_destination_cannot_be_memory_database(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        try:
            store.backup_to(":memory:")
        except ValueError as exc:
            assert "file-backed" in str(exc)
        else:
            raise AssertionError("in-memory backup destination must be rejected")
    finally: store.close()
