import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_execution_id_cannot_be_bound_to_two_keys(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('key-356-a','charge',{'amount':356},execution_id='shared-exec')
        with pytest.raises(IdempotencyConflict, match='already bound'):
            store.claim('key-356-b','charge',{'amount':357},execution_id='shared-exec')
        assert store.get('key-356-a') is not None
        assert store.get('key-356-b') is None
        assert store.count_execution_bindings('shared-exec') == 1
    finally: store.close()
