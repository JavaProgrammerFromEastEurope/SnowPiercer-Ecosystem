import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_blank_reconciliation_evidence_is_rejected_before_state_change(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('key-355','charge',{'amount':355},execution_id='exec-355')
        store.mark_unknown('key-355','provider timeout')
        before=store.get('key-355')
        with pytest.raises(ValueError, match='evidence'):
            store.reconcile_completed('key-355',{'accepted':True},evidence='  ',execution_id='exec-355')
        assert store.get('key-355') == before
    finally: store.close()
