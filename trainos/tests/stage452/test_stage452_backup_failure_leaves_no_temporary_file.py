from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_backup_failure_leaves_no_temporary_file(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    destination = tmp_path / "backup.db"
    def fail(_path): return ("injected validation failure",)
    monkeypatch.setattr(CommandIdempotencyStore, "validate_backup", classmethod(lambda cls, path: fail(path)))
    try:
        import pytest
        with pytest.raises(Exception, match="backup validation failed"):
            store.backup_to(destination)
    finally: store.close()
    assert not destination.exists()
    assert list(tmp_path.glob(".backup.db.*.tmp")) == []
