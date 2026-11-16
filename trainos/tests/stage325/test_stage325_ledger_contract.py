from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
def test_completed_reconciliation_audit_has_evidence_and_generation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-325', 'move', {'x': 1}, execution_id='exec-325')
        assert store.reserve_dispatch('key-325') is True
        store.mark_unknown('key-325', 'ack timeout')
        completed = store.reconcile_completed('key-325', {'ok': True}, evidence='provider receipt 325', execution_id='exec-325')
        row = store._connection.execute('SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=?', ('key-325',)).fetchone()
        assert completed.status.value == 'completed' and tuple(row) == ('provider receipt 325', 'completed', 1)
    finally: store.close()
