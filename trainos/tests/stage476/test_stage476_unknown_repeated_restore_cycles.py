from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_remains_unknown_after_repeated_backup_restore(tmp_path):
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("k", "charge", {"cents": 10})
    store.mark_unknown("k", reason="provider acknowledgement missing")
    store.close()
    current = source
    for index in range(3):
        opened = CommandIdempotencyStore(current)
        backup = tmp_path / f"backup-{index}.db"
        opened.backup_to(backup)
        assert opened.get("k").status is IdempotencyStatus.UNKNOWN
        opened.close()
        assert CommandIdempotencyStore.validate_backup(backup) == ()
        current = backup
    final_store = CommandIdempotencyStore(current)
    try:
        assert final_store.get("k").status is IdempotencyStatus.UNKNOWN
        assert final_store.check_integrity() == ()
    finally:
        final_store.close()
