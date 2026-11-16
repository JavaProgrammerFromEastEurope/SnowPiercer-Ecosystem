import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_completed_reconciliation_rolls_back_if_audit_insert_fails(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-283", "move", {"x": 1}, execution_id="exec-283")
        store.mark_unknown("key-283", "ack timeout")
        with store._connection:
            store._ensure_reconciliation_table()
            store._connection.execute(
                "CREATE TRIGGER reject_completed_audit BEFORE INSERT ON command_idempotency_reconciliation "
                "WHEN NEW.decision='completed' BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END"
            )
        before = store.get("key-283")
        with pytest.raises(sqlite3.IntegrityError, match="audit unavailable"):
            store.reconcile_completed("key-283", {"ok": True}, evidence="receipt-283", execution_id="exec-283")
        assert store.get("key-283") == before
        assert store.get("key-283").status is IdempotencyStatus.UNKNOWN
        assert store._connection.execute(
            "SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key='key-283'"
        ).fetchone()[0] == 0
    finally:
        store.close()
