from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_repeated_same_completed_reconciliation_does_not_duplicate_audit(tmp_path):
    s=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        s.claim('k377','charge',{'amount':377},execution_id='e377'); s.mark_unknown('k377','timeout')
        result={'provider':'confirmed','reference':'r377'}
        first=s.reconcile_completed('k377',result,evidence='receipt r377',execution_id='e377')
        before=s._connection.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key='k377'").fetchone()[0]
        second=s.reconcile_completed('k377',{'reference':'r377','provider':'confirmed'},evidence='different repeat evidence',execution_id='e377')
        after=s._connection.execute("SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key='k377'").fetchone()[0]
        assert second == first and before == after == 1
    finally: s.close()
