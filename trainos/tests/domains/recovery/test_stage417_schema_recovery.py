import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_end_to_end_migrate_backup_restore_and_unknown_reopen(tmp_path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    store.claim("unknown-417", "submit_order", {"order": 417}, execution_id="exec-417")
    assert store.reserve_dispatch("unknown-417") is True
    store.mark_unknown("unknown-417", "remote outcome unavailable")
    assert store.check_integrity() == ()
    destination = sqlite3.connect(backup)
    try: store._connection.backup(destination)
    finally: destination.close()
    store.close()
    restored = CommandIdempotencyStore(backup)
    try:
        record = restored.get("unknown-417")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.dispatch_started is True
        assert record.dispatch_generation == 1
        assert restored.claim("unknown-417", "submit_order", {"order": 417}).created is False
        assert restored.check_integrity() == ()
    finally: restored.close()
