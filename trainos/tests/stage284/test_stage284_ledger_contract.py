import sqlite3
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_not_executed_reconciliation_rolls_back_if_audit_insert_fails(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-284", "move", {"x": 1}, execution_id="exec-284")
        store.mark_unknown("key-284", "ack timeout")
        with store._connection:
            store._ensure_reconciliation_table()
            store._connection.execute(
                "CREATE TRIGGER reject_not_executed_audit BEFORE INSERT ON command_idempotency_reconciliation "
                "WHEN NEW.decision='not_executed' BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END"
            )
        before = store.get("key-284")
        with pytest.raises(sqlite3.IntegrityError, match="audit unavailable"):
            store.reconcile_not_executed("key-284", evidence="provider-absent", execution_id="exec-284")
        assert store.get("key-284") == before
        assert store.get("key-284").status is IdempotencyStatus.UNKNOWN
        assert store._connection.execute(
            "SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key='key-284'"
        ).fetchone()[0] == 0
    finally:
        store.close()
