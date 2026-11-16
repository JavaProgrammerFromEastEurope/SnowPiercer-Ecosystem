from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
def test_repeated_completed_reconciliation_does_not_duplicate_audit(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-324', 'move', {'x': 1}, execution_id='exec-324')
        store.mark_unknown('key-324', 'ack timeout')
        first = store.reconcile_completed('key-324', {'ok': True}, evidence='receipt-324', execution_id='exec-324')
        count_before = store._connection.execute('SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?', ('key-324',)).fetchone()[0]
        repeated = store.reconcile_completed('key-324', {'ok': True}, evidence='receipt-repeat', execution_id='exec-324')
        count_after = store._connection.execute('SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?', ('key-324',)).fetchone()[0]
        assert repeated == first and count_after == count_before == 1
    finally: store.close()
