import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_duplicate_completion_does_not_mutate_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-359', 'charge', {'amount': 359}, execution_id='exec-359')
        original = store.complete('key-359', {'accepted': True}, execution_id='exec-359')
        with pytest.raises(IdempotencyConflict, match='conflicting duplicate'):
            store.complete('key-359', {'accepted': False}, execution_id='exec-359')
        assert store.get('key-359') == original
    finally:
        store.close()
