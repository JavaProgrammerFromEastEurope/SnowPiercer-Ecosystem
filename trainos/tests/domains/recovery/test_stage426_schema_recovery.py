import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_backup_restore_preserves_unknown_without_implicit_retry(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    store.claim("uncertain", "charge", {"cents": 500}, execution_id="exec-uncertain")
    assert store.reserve_dispatch("uncertain") is True
    store.mark_unknown("uncertain", "provider timeout")
    try:
        store.backup_to(backup)
    finally: store.close()
    restored = CommandIdempotencyStore(backup)
    try:
        record = restored.get("uncertain")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.dispatch_started is True
        assert restored.claim("uncertain", "charge", {"cents": 500}).created is False
        assert restored.check_integrity() == ()
    finally: restored.close()
