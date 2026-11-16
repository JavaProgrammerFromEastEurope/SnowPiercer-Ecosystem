import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_completed_reconciliation_audit_records_generation_and_evidence(tmp_path):
    database = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(database)
    try:
        store.claim("key-345", "charge", {"amount": 345}, execution_id="exec-345")
        assert store.reserve_dispatch("key-345") is True
        store.mark_unknown("key-345", "provider timeout")
        record = store.reconcile_completed(
            "key-345", {"accepted": True}, evidence="provider receipt 345", execution_id="exec-345"
        )
        assert record.status is IdempotencyStatus.COMPLETED
        assert record.dispatch_generation == 1
        row = store._connection.execute(
            "SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation "
            "WHERE idempotency_key = ? ORDER BY sequence DESC LIMIT 1", ("key-345",)
        ).fetchone()
        assert tuple(row) == ("provider receipt 345", "completed", 1)
    finally:
        store.close()
