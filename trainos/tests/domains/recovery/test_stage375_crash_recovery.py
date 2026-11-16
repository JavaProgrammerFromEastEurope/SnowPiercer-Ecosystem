import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyConflict

def test_wrong_execution_identity_after_reopen_cannot_change_unknown_record(tmp_path):
    db=tmp_path/'ledger.sqlite3'; s=CommandIdempotencyStore(db)
    s.claim('k375','charge',{'amount':375},execution_id='e375'); s.mark_unknown('k375','interrupted')
    expected=s.get('k375'); s.close(); s=CommandIdempotencyStore(db)
    try:
        with pytest.raises(IdempotencyConflict,match='does not match'):
            s.reconcile_completed('k375',{'receipt':'r'},evidence='some receipt',execution_id='wrong')
        assert s.get('k375') == expected
        assert s._connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_idempotency_reconciliation'").fetchone() is None
    finally: s.close()
