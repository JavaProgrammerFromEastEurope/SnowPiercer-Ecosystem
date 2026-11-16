import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_completion_requires_execution_id_for_bound_command(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('key-348','charge',{'amount':348},execution_id='exec-348')
        before=store.get('key-348')
        with pytest.raises(IdempotencyConflict):
            store.complete('key-348',{'accepted':True})
        assert store.get('key-348') == before
    finally: store.close()
