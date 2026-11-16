import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_unknown_reason_is_idempotent_but_conflicts_are_rejected(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        store.claim('key-360', 'charge', {'amount': 360}, execution_id='exec-360')
        first = store.mark_unknown('key-360', 'provider timeout')
        assert store.mark_unknown('key-360', 'provider timeout') == first
        with pytest.raises(IdempotencyConflict):
            store.mark_unknown('key-360', 'different failure')
        assert store.get('key-360') == first
    finally:
        store.close()
