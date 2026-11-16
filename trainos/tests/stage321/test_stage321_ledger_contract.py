from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
def test_repeating_same_unknown_reason_is_idempotent(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-321', 'move', {'x': 1}, execution_id='exec-321')
        first = store.mark_unknown('key-321', 'ack timeout')
        second = store.mark_unknown('key-321', 'ack timeout')
        assert second == first and store.get('key-321') == first
    finally: store.close()
