from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_restored_audit_persists_after_reopen(tmp_path):
    source = tmp_path / "source.db"; store = CommandIdempotencyStore(source)
    store.claim("key", "cmd", {"v": 1}); store.mark_unknown("key", reason="timeout")
    store.reconcile_not_executed("key", evidence="provider confirmed not sent")
    backup = tmp_path / "backup.db"
    try: store.backup_to(backup)
    finally: store.close()
    restored = CommandIdempotencyStore(backup)
    try:
        rows = restored._connection.execute("SELECT evidence, decision, recorded_at FROM command_idempotency_reconciliation").fetchall()
        assert len(rows) == 1 and rows[0]["evidence"] == "provider confirmed not sent"
        assert rows[0]["decision"] == "not_executed" and rows[0]["recorded_at"]
    finally: restored.close()
