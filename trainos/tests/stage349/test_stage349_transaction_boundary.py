import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_completion_rejects_mismatched_execution_id_without_mutation(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('key-349','charge',{'amount':349},execution_id='exec-349')
        before=store.get('key-349')
        with pytest.raises(IdempotencyConflict):
            store.complete('key-349',{'accepted':True},execution_id='other-exec')
        assert store.get('key-349') == before
    finally: store.close()
