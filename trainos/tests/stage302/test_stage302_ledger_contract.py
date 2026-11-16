from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_not_executed_reconciliation_persists_evidence_and_generation(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("key-302", "move", {"x": 1}, execution_id="exec-302")
    store.reserve_dispatch("key-302")
    store.mark_unknown("key-302", "ack timeout")
    record = store.reconcile_not_executed("key-302", evidence="provider confirms absent", execution_id="exec-302")
    assert record.status is IdempotencyStatus.CLAIMED
    assert record.dispatch_started is False
    rows = store._connection.execute("SELECT evidence, dispatch_generation, decision FROM command_idempotency_reconciliation WHERE idempotency_key=?", ("key-302",)).fetchall()
    store.close()
    reopened = CommandIdempotencyStore(path)
    try:
        assert len(rows) == 1
        assert tuple(rows[0]) == ("provider confirms absent", 1, "not_executed")
        assert reopened.get("key-302") == record
    finally:
        reopened.close()
