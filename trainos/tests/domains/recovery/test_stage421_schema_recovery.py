import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_snapshot_is_independent_of_later_source_writes(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    store.claim("before", "record", {"n": 1})
    try:
        store.backup_to(backup)
        store.claim("after", "record", {"n": 2})
        restored = CommandIdempotencyStore(backup)
        try:
            assert restored.get("before") is not None
            assert restored.get("after") is None
        finally: restored.close()
    finally: store.close()
