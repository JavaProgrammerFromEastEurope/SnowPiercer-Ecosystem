import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_restore_preserves_completed_result(tmp_path):
    source = tmp_path / "source.sqlite3"; backup = tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    store.claim("k402", "charge", {"amount": 402})
    store.complete("k402", {"ok": True, "receipt": "r402"})
    destination = sqlite3.connect(backup)
    try: store._connection.backup(destination)
    finally: destination.close(); store.close()
    restored = CommandIdempotencyStore(backup)
    try:
        record = restored.get("k402")
        assert record.status.value == "completed"
        assert record.result == {"ok": True, "receipt": "r402"}
        assert restored.check_integrity() == ()
    finally: restored.close()
