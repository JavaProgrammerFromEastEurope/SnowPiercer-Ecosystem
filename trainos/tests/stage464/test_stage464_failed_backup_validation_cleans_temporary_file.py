import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_failed_validation_removes_temporary_backup(monkeypatch, tmp_path):
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("k", "charge", {"cents": 10})
    monkeypatch.setattr(CommandIdempotencyStore, "validate_backup", classmethod(lambda cls, path: ("forced failure",)))
    with pytest.raises(Exception, match="backup validation failed"):
        store.backup_to(tmp_path / "backup.db")
    assert not (tmp_path / "backup.db").exists()
    assert list(tmp_path.glob(".backup.db.*.tmp")) == []
    store.close()
