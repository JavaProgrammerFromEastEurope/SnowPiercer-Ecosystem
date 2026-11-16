from tests.sqlite_resource_helpers import managed_sqlite_connection
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

def test_corrupt_audit_is_rejected_without_mutating_backup(tmp_path):
    import hashlib
    backup = make_backup(tmp_path)
    with managed_sqlite_connection(backup) as conn:
        conn.execute("UPDATE command_idempotency_reconciliation SET dispatch_generation=999")
    before = hashlib.sha256(backup.read_bytes()).hexdigest()
    findings = CommandIdempotencyStore.validate_backup(backup)
    after = hashlib.sha256(backup.read_bytes()).hexdigest()
    assert findings
    assert before == after
