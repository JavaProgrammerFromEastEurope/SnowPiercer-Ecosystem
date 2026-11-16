from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_explicit_not_executed_reconciliation_resets_reservation_without_resetting_generation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-343", "charge", {"amount": 343}, execution_id="exec-343")
        assert store.reserve_dispatch("key-343") is True
        store.mark_unknown("key-343", "provider timeout")
        record = store.reconcile_not_executed(
            "key-343", evidence="provider confirms no charge", execution_id="exec-343"
        )
        assert record.status is IdempotencyStatus.CLAIMED
        assert record.dispatch_started is False
        assert record.dispatch_generation == 1
    finally:
        store.close()
