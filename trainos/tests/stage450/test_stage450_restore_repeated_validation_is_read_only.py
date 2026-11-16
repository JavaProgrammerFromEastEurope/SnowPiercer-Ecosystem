from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_restore_repeated_validation_is_read_only(tmp_path):
    store = make_store(tmp_path)
    try:
        store.claim("key", "cmd", {"v": 1})
        backup = tmp_path / "backup.db"; store.backup_to(backup)
    finally: store.close()
    before = backup.read_bytes()
    for _ in range(3): assert CommandIdempotencyStore.validate_backup(backup) == ()
    assert backup.read_bytes() == before
