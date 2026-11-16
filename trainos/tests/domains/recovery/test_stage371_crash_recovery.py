import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_old_not_executed_evidence_cannot_be_reused_for_later_generation(tmp_path):
    s=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        s.claim('k371','charge',{'amount':371},execution_id='e371'); s.reserve_dispatch('k371')
        s.mark_unknown('k371','timeout one')
        s.reconcile_not_executed('k371',evidence='provider snapshot generation one',execution_id='e371')
        assert s.reserve_dispatch('k371') is True
        s.mark_unknown('k371','timeout two'); before=s.get('k371')
        with pytest.raises(IdempotencyConflict,match='predates a later dispatch'):
            s.reconcile_not_executed('k371',evidence='provider snapshot generation one',execution_id='e371')
        assert s.get('k371') == before
    finally: s.close()
