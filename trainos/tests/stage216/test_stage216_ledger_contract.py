from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_reconciliation_allows_new_generation_only_after_explicit_proof(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-216", "move", {"x": 1}, execution_id="exec-216")
        assert store.reserve_dispatch("key-216") is True
        store.mark_unknown("key-216", "ack timeout")
        reconciled = store.reconcile_not_executed("key-216", evidence="provider-proof-216", execution_id="exec-216")
        assert reconciled.status is IdempotencyStatus.CLAIMED
        assert reconciled.dispatch_generation == 1
        assert reconciled.dispatch_started is False
        assert store.reserve_dispatch("key-216") is True
        after = store.get("key-216")
        assert after.dispatch_generation == 2
        assert after.dispatch_started is True
    finally:
        store.close()
