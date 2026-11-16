import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_backup_preserves_reconciliation_audit(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    try:
        store.claim("audit", "charge", {"cents": 700}, execution_id="exec-audit")
        store.reserve_dispatch("audit")
        store.mark_unknown("audit", "timeout")
        store.reconcile_completed("audit", {"receipt": "r-1"}, evidence="provider receipt", execution_id="exec-audit")
        store.backup_to(backup)
    finally:
        store.close()
    assert CommandIdempotencyStore.validate_backup(backup) == ()
    restored = CommandIdempotencyStore(backup)
    try:
        assert restored.get("audit").status is IdempotencyStatus.COMPLETED
        assert restored._connection.execute("SELECT evidence FROM command_idempotency_reconciliation").fetchone()[0] == "provider receipt"
    finally:
        restored.close()
