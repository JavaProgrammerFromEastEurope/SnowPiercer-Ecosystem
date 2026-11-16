from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_iso8601_utc_audit_timestamp_is_accepted(tmp_path):
    db = tmp_path / "ledger.db"
    store = CommandIdempotencyStore(db)
    store.claim("k", "charge", {"cents": 10})
    store.mark_unknown("k", reason="timeout")
    store.reconcile_completed("k", {"ok": True}, evidence="provider-confirmed")
    store.close()
    assert CommandIdempotencyStore.validate_backup(db) == ()
