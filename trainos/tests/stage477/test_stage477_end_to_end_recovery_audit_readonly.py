from tests.sqlite_resource_helpers import managed_sqlite_connection
import hashlib
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def test_end_to_end_restore_preserves_audit_and_validator_is_read_only(tmp_path):
    source = tmp_path / "source.db"
    store = CommandIdempotencyStore(source)
    store.claim("k", "charge", {"cents": 10})
    store.mark_unknown("k", reason="provider acknowledgement missing")
    store.reconcile_completed("k", {"provider_ref": "ref-1"}, evidence="provider lookup confirmed completion")
    backup = tmp_path / "backup.db"
    store.backup_to(backup)
    store.close()
    before = digest(backup)
    assert CommandIdempotencyStore.validate_backup(backup) == ()
    assert digest(backup) == before
    restored = CommandIdempotencyStore(backup)
    try:
        assert restored.get("k").status is IdempotencyStatus.COMPLETED
        assert restored.check_integrity() == ()
        import sqlite3
        with managed_sqlite_connection(backup) as conn:
            rows = conn.execute("SELECT idempotency_key,evidence,decision FROM command_idempotency_reconciliation ORDER BY sequence").fetchall()
        assert rows == [("k", "provider lookup confirmed completion", "completed")]
    finally:
        restored.close()
