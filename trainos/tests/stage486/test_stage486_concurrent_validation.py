import sqlite3
from pathlib import Path
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def make_backup(tmp_path: Path) -> Path:
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("key-1", "charge", {"cents": 250})
    store.mark_unknown("key-1", reason="provider response missing")
    store.reconcile_completed("key-1", {"provider_ref": "ref-1"}, evidence="provider lookup confirmed completion")
    backup = tmp_path / "backup.db"
    store.backup_to(backup)
    store.close()
    return backup

def test_concurrent_validation_of_same_backup_is_stable(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    backup = make_backup(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(CommandIdempotencyStore.validate_backup, [backup] * 32))
    assert results == [()] * 32
