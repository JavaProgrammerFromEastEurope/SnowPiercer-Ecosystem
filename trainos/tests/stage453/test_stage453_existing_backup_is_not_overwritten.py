from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_existing_backup_is_not_overwritten(tmp_path):
    store = make_store(tmp_path); destination = tmp_path / "backup.db"
    destination.write_bytes(b"preserve-me")
    try:
        import pytest
        with pytest.raises(FileExistsError): store.backup_to(destination)
    finally: store.close()
    assert destination.read_bytes() == b"preserve-me"
