from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
def test_execution_binding_diagnostics_count_exact_identifier(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-326', 'move', {'x': 1}, execution_id='exec-326')
        assert store.count_execution_bindings('exec-326') == 1
        assert store.count_execution_bindings('exec-other-326') == 0
    finally: store.close()
