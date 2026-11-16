from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_repeated_backup_cycles_preserve_records(tmp_path):
    source = tmp_path / "ledger.db"; store = CommandIdempotencyStore(source)
    try:
        store.claim("key", "cmd", {"v": 1})
        for i in range(3):
            backup = tmp_path / f"backup-{i}.db"; store.backup_to(backup)
            assert CommandIdempotencyStore.validate_backup(backup) == ()
            restored = CommandIdempotencyStore(backup)
            try: assert restored.get("key").status is IdempotencyStatus.CLAIMED
            finally: restored.close()
    finally: store.close()
