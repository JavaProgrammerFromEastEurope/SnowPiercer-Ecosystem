import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict
def test_conflicting_duplicate_completion_does_not_mutate_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-319', 'move', {'x': 1}, execution_id='exec-319')
        first = store.complete('key-319', {'ok': True}, execution_id='exec-319')
        with pytest.raises(IdempotencyConflict, match='conflicting duplicate command result'):
            store.complete('key-319', {'ok': False}, execution_id='exec-319')
        assert store.get('key-319') == first
    finally: store.close()
