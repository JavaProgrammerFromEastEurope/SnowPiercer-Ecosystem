import sqlite3

import pytest

from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_orphan_reconciliation_audit_is_rejected_before_backup_publish(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    store = CommandIdempotencyStore(source)
    try:
        store.claim("k", "noop", {})
        store._ensure_reconciliation_table()
        store._connection.execute(
            "INSERT INTO command_idempotency_reconciliation"
            "(idempotency_key,evidence,decision,dispatch_generation) "
            "VALUES('missing','evidence','not_executed',0)"
        )
        store._connection.commit()
        with pytest.raises(sqlite3.DatabaseError, match="orphan idempotency key"):
            store.backup_to(backup)
    finally:
        store.close()

    assert not backup.exists()
    assert not list(tmp_path.glob(".backup.db.*.tmp"))
