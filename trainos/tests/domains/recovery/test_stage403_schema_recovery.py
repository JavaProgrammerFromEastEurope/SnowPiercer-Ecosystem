import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_restore_preserves_reconciliation_and_audit(tmp_path):
    source = tmp_path / "source.sqlite3"; backup = tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    store.claim("k403", "charge", {"amount": 403}, execution_id="exec403")
    store.mark_unknown("k403", "timeout")
    store.reconcile_completed("k403", {"ok": True}, evidence="provider receipt", execution_id="exec403")
    destination = sqlite3.connect(backup)
    try: store._connection.backup(destination)
    finally: destination.close(); store.close()
    restored = CommandIdempotencyStore(backup)
    try:
        audit = restored._connection.execute("SELECT idempotency_key,evidence,decision,dispatch_generation FROM command_idempotency_reconciliation").fetchall()
        assert len(audit) == 1
        assert tuple(audit[0]) == ("k403", "provider receipt", "completed", 0)
        assert restored.get("k403").result == {"ok": True}
        assert restored.check_integrity() == ()
    finally: restored.close()
