import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_empty_reconciliation_evidence_is_rejected_without_mutation(tmp_path):
    s=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        s.claim('k372','charge',{'amount':372},execution_id='e372'); s.mark_unknown('k372','timeout')
        before=s.get('k372')
        with pytest.raises(ValueError,match='evidence must not be empty'):
            s.reconcile_completed('k372',{'accepted':True},evidence='   ',execution_id='e372')
        assert s.get('k372') == before
        assert s._connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone() is None
    finally: s.close()
