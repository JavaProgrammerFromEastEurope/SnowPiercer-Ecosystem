import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_end_to_end_unknown_recovery_stays_non_retryable(tmp_path):
    source, backup = tmp_path / "source.sqlite3", tmp_path / "backup.sqlite3"
    store = CommandIdempotencyStore(source)
    try:
        store.claim("unknown-e2e", "charge", {"cents": 1200}, execution_id="exec-e2e")
        store.reserve_dispatch("unknown-e2e")
        store.mark_unknown("unknown-e2e", "provider unavailable")
        store.backup_to(backup)
    finally:
        store.close()
    assert CommandIdempotencyStore.validate_backup(backup) == ()
    restored = CommandIdempotencyStore(backup)
    try:
        record = restored.get("unknown-e2e")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.dispatch_started is True
        assert restored.claim("unknown-e2e", "charge", {"cents": 1200}).created is False
        assert restored.check_integrity() == ()
    finally:
        restored.close()
