from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_reconcile_completed_persists_record_and_audit_in_one_transaction(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    try:
        store.claim("key-217", "move", {"x": 1}, execution_id="exec-217")
        store.reserve_dispatch("key-217")
        store.mark_unknown("key-217", "ack timeout")
        result = store.reconcile_completed("key-217", {"ok": True}, evidence="provider-proof-217", execution_id="exec-217")
        assert result.status is IdempotencyStatus.COMPLETED
        row = store._connection.execute("SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=? ORDER BY sequence DESC LIMIT 1", ("key-217",)).fetchone()
        assert tuple(row) == ("provider-proof-217", "completed", 1)
        store.close()
        reopened = CommandIdempotencyStore(path)
        try:
            assert reopened.get("key-217").status is IdempotencyStatus.COMPLETED
            assert reopened.get("key-217").result == {"ok": True}
            assert tuple(reopened._connection.execute("SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=? ORDER BY sequence DESC LIMIT 1", ("key-217",)).fetchone()) == ("provider-proof-217", "completed", 1)
        finally:
            reopened.close()
    finally:
        try: store.close()
        except Exception: pass
