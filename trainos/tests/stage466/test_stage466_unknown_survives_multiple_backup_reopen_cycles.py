from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_survives_multiple_backup_reopen_cycles(tmp_path):
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("k", "charge", {"cents": 10})
    store.mark_unknown("k", reason="ack timeout")
    store.close()
    current = source
    for index in range(2):
        opened = CommandIdempotencyStore(current)
        backup = tmp_path / f"backup-{index}.db"
        opened.backup_to(backup)
        opened.close()
        current = backup
    restored = CommandIdempotencyStore(current)
    try:
        record = restored.get("k")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert restored.claim("k", "charge", {"cents": 10}).created is False
    finally:
        restored.close()
