from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_canonical_result_key_order_does_not_create_conflict(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-367', 'charge', {'amount': 367}, execution_id='exec-367')
        first = store.complete('key-367', {'z': 1, 'a': {'y': 2, 'b': 3}}, execution_id='exec-367')
        second = store.complete('key-367', {'a': {'b': 3, 'y': 2}, 'z': 1}, execution_id='exec-367')
        assert second == first
    finally:
        store.close()
