from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_reconciliation_and_audit_survive_database_reopen(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(db)
    store.claim("key-247", "move", {"x": 1}, execution_id="exec-247")
    store.reserve_dispatch("key-247")
    store.mark_unknown("key-247", "ack timeout")
    store.reconcile_completed("key-247", {"ok": True}, evidence="external-record-247", execution_id="exec-247")
    store.close()

    reopened = CommandIdempotencyStore(db)
    try:
        record = reopened.get("key-247")
        assert record.status is IdempotencyStatus.COMPLETED
        assert record.result == {"ok": True}
        row = reopened._connection.execute(
            "SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=?",
            ("key-247",),
        ).fetchone()
        assert tuple(row) == ("external-record-247", "completed", 1)
    finally:
        reopened.close()
