from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_missing_execution_index_is_reported_without_repair(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('k390','charge',{'amount':390},execution_id='e390')
        store._connection.execute('DROP INDEX idx_command_idempotency_execution_id')
        findings=store.check_integrity()
        assert any('uniqueness index is missing' in f for f in findings)
        indexes={r['name'] for r in store._connection.execute('PRAGMA index_list(command_idempotency)')}
        assert 'idx_command_idempotency_execution_id' not in indexes
    finally: store.close()
