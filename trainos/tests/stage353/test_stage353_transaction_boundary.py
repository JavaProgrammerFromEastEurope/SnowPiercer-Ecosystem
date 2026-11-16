import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_unknown_outcome_cannot_be_completed_without_reconciliation(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('key-353','charge',{'amount':353},execution_id='exec-353')
        store.mark_unknown('key-353','provider timeout')
        before=store.get('key-353')
        with pytest.raises(ValueError, match='reconciled'):
            store.complete('key-353',{'accepted':True},execution_id='exec-353')
        assert store.get('key-353') == before
    finally: store.close()
