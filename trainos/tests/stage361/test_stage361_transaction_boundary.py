from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_not_executed_reconciliation_updates_state_and_audit_together(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-361', 'charge', {'amount': 361}, execution_id='exec-361')
        store.reserve_dispatch('key-361')
        store.mark_unknown('key-361', 'provider timeout')
        record = store.reconcile_not_executed('key-361', evidence='provider confirms no operation', execution_id='exec-361')
        assert record.status is IdempotencyStatus.CLAIMED
        assert record.dispatch_started is False
        row = store._connection.execute(
            "SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=?",
            ('key-361',)
        ).fetchone()
        assert tuple(row) == ('provider confirms no operation', 'not_executed', 1)
    finally:
        store.close()
