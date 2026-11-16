from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_duplicate_completed_reconciliation_does_not_duplicate_audit_entry(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-225", "move", {"x": 1}, execution_id="exec-225")
        store.reserve_dispatch("key-225")
        store.mark_unknown("key-225", "ack timeout")
        store.reconcile_completed("key-225", {"ok": True}, evidence="proof-225", execution_id="exec-225")
        before = store._connection.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?", ("key-225",)).fetchone()[0]
        store.reconcile_completed("key-225", {"ok": True}, evidence="proof-225-repeat", execution_id="exec-225")
        after = store._connection.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?", ("key-225",)).fetchone()[0]
        assert before == after == 1
    finally:
        store.close()
