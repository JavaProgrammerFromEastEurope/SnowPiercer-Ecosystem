import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_non_json_result_is_rejected_without_mutating_ledger(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('key-352','charge',{'amount':352},execution_id='exec-352')
        before=store.get('key-352')
        with pytest.raises(ValueError, match='JSON-serializable'):
            store.complete('key-352',{'unsupported':object()},execution_id='exec-352')
        assert store.get('key-352') == before
    finally: store.close()
