from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_duplicate_completed_reconciliation_does_not_duplicate_audit_row(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-276", "move", {"x": 1}, execution_id="exec-276")
        store.mark_unknown("key-276", "ack timeout")
        first = store.reconcile_completed("key-276", {"ok": True}, evidence="receipt-276", execution_id="exec-276")
        second = store.reconcile_completed("key-276", {"ok": True}, evidence="receipt-276", execution_id="exec-276")
        assert second == first
        count = store._connection.execute(
            "SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?", ("key-276",)
        ).fetchone()[0]
        assert count == 1
    finally:
        store.close()
