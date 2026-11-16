import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_existing_destination_is_never_overwritten(tmp_path):
    source=tmp_path/'source.db'; target=tmp_path/'backup.db'; target.write_bytes(b'keep-me')
    store=CommandIdempotencyStore(source)
    try:
        with pytest.raises(FileExistsError): store.backup_to(target)
    finally: store.close()
    assert target.read_bytes()==b'keep-me'
