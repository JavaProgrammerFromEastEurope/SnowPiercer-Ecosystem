from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
def test_same_completion_is_idempotent(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-318', 'move', {'x': 1}, execution_id='exec-318')
        first = store.complete('key-318', {'ok': True, 'n': 1}, execution_id='exec-318')
        repeated = store.complete('key-318', {'n': 1, 'ok': True}, execution_id='exec-318')
        assert repeated == first
        assert store.get('key-318') == first
    finally: store.close()
