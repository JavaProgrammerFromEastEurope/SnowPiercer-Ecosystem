from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_integrity_check_does_not_mutate_unknown_state_or_audit(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("k387", "charge", {"amount": 387}, execution_id="e387")
        store.reserve_dispatch("k387")
        before = store.mark_unknown("k387", "acknowledgement lost")
        after_first = store._connection.execute(
            "SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key='k387'"
        ).fetchone()[0] if store._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'"
        ).fetchone() else 0
        findings = store.check_integrity()
        after = store.get("k387")
        after_count = store._connection.execute(
            "SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key='k387'"
        ).fetchone()[0] if store._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'"
        ).fetchone() else 0
        assert findings == ()
        assert after == before
        assert after_count == after_first == 0
    finally:
        store.close()
