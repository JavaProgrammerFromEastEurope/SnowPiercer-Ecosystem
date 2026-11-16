import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_conflicting_repeated_claim_does_not_mutate_original_record(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        first=store.claim('key-351','charge',{'amount':351},execution_id='exec-351')
        with pytest.raises(IdempotencyConflict):
            store.claim('key-351','refund',{'amount':351},execution_id='exec-351')
        assert store.get('key-351') == first.record
    finally: store.close()
