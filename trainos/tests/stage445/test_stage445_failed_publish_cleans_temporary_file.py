import os
import pytest
from kernel.command.execution import command_idempotency_store as module
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_failed_atomic_publish_cleans_temporary_file(tmp_path, monkeypatch):
    db=tmp_path/'ledger.db'; target=tmp_path/'backup.db'; store=CommandIdempotencyStore(db)
    monkeypatch.setattr(module.os, 'link', lambda *a, **k: (_ for _ in ()).throw(OSError('simulated publish failure')))
    try:
        with pytest.raises(OSError, match='simulated publish failure'): store.backup_to(target)
    finally: store.close()
    assert not target.exists()
    assert not list(tmp_path.glob('.backup.db.*.tmp'))
