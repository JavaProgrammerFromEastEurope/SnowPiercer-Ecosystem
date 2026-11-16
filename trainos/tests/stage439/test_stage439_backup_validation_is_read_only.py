import os
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_backup_validation_does_not_change_backup_bytes(tmp_path):
    source=tmp_path/'source.db'; backup=tmp_path/'backup.db'
    store=CommandIdempotencyStore(source)
    try: store.claim('k','noop',{'v':1}); store.backup_to(backup)
    finally: store.close()
    before=backup.read_bytes(); findings=CommandIdempotencyStore.validate_backup(backup)
    assert findings==()
    assert backup.read_bytes()==before
