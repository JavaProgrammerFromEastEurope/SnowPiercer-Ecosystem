from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_completed_reconciliation_audit_matches_generation_after_reopen(tmp_path):
    db=tmp_path/'ledger.sqlite3'; s=CommandIdempotencyStore(db)
    s.claim('k374','charge',{'amount':374},execution_id='e374'); s.reserve_dispatch('k374')
    s.mark_unknown('k374','acknowledgement lost')
    expected=s.reconcile_completed('k374',{'receipt':'r374'},evidence='provider receipt r374',execution_id='e374')
    row=s._connection.execute("SELECT evidence,decision,dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key='k374'").fetchone()
    s.close(); s=CommandIdempotencyStore(db)
    try:
        assert s.get('k374') == expected
        row2=s._connection.execute("SELECT evidence,decision,dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key='k374'").fetchone()
        assert tuple(row2) == tuple(row) == ('provider receipt r374','completed',1)
    finally: s.close()
