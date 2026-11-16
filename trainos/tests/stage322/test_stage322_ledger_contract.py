import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict
def test_conflicting_unknown_reason_does_not_mutate_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-322', 'move', {'x': 1}, execution_id='exec-322')
        first = store.mark_unknown('key-322', 'ack timeout')
        with pytest.raises(IdempotencyConflict, match='conflicting unknown-outcome reason'):
            store.mark_unknown('key-322', 'network reset')
        assert store.get('key-322') == first
    finally: store.close()
