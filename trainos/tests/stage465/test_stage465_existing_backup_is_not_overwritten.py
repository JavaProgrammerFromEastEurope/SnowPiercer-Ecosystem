import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_existing_backup_bytes_are_preserved(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "source.db")
    destination = tmp_path / "backup.db"
    destination.write_bytes(b"keep-this-file")
    with pytest.raises(FileExistsError):
        store.backup_to(destination)
    assert destination.read_bytes() == b"keep-this-file"
    store.close()
