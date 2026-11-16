from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_end_to_end_backup_recovery_unknown_and_audit(tmp_path):
    source = tmp_path / "source.db"; store = CommandIdempotencyStore(source)
    store.claim("key", "cmd", {"amount": 7}); store.mark_unknown("key", reason="ack timeout")
    backup = tmp_path / "backup.db"
    try: store.backup_to(backup)
    finally: store.close()
    assert CommandIdempotencyStore.validate_backup(backup) == ()
    restored = CommandIdempotencyStore(backup)
    try:
        record = restored.get("key")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert restored.claim("key", "cmd", {"amount": 7}).created is False
        tables = {row[0] for row in restored._connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "command_idempotency_reconciliation" in tables:
            assert restored._connection.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation").fetchone()[0] == 0
    finally: restored.close()
