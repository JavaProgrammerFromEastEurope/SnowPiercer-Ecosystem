import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_to_creates_consistent_reopenable_snapshot(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    store.claim("snap-a", "record", {"n": 1})
    store.claim("snap-b", "record", {"n": 2})
    try:
        assert store.backup_to(backup) == str(backup)
        restored = CommandIdempotencyStore(backup)
        try:
            assert restored.get("snap-a") is not None
            assert restored.get("snap-b") is not None
            assert restored.check_integrity() == ()
        finally: restored.close()
    finally: store.close()
