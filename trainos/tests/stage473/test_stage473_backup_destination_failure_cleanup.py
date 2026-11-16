from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
import pytest

def test_backup_destination_failure_does_not_create_temp_files(tmp_path):
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("k", "charge", {"cents": 10})
    destination = tmp_path / "missing" / "backup.db"
    with pytest.raises(ValueError, match="parent directory must exist"):
        store.backup_to(destination)
    assert list(tmp_path.glob(".backup.db.*.tmp")) == []
    store.close()
