import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_sqlite_backup_preserves_claimed_command(tmp_path):
    source = tmp_path / "source.sqlite3"; backup = tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    try:
        store.claim("k401", "charge", {"amount": 401}, execution_id="exec401")
        destination = sqlite3.connect(backup)
        try: store._connection.backup(destination)
        finally: destination.close()
    finally: store.close()
    restored = CommandIdempotencyStore(backup)
    try:
        record = restored.get("k401")
        assert record is not None and record.execution_id == "exec401"
        assert record.status.value == "claimed" and restored.check_integrity() == ()
    finally: restored.close()
