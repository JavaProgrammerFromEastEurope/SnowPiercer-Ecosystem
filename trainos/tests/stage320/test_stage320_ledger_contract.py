import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore
def test_blank_unknown_reason_is_rejected_without_mutation(tmp_path):
    store = CommandIdempotencyStore(tmp_path / 'ledger.sqlite3')
    try:
        before = store.claim('key-320', 'move', {'x': 1}, execution_id='exec-320').record
        for reason in ('', '   '):
            with pytest.raises(ValueError, match='reason must not be empty'):
                store.mark_unknown('key-320', reason)
            assert store.get('key-320') == before
    finally: store.close()
