import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_completed_record_cannot_be_reclassified_as_not_executed(tmp_path):
    s=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        s.claim('k376','charge',{'amount':376},execution_id='e376')
        before=s.complete('k376',{'accepted':True},execution_id='e376')
        with pytest.raises(ValueError,match='only unknown outcomes'):
            s.reconcile_not_executed('k376',evidence='contradictory evidence',execution_id='e376')
        assert s.get('k376') == before
        assert s._connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone() is None
    finally: s.close()
