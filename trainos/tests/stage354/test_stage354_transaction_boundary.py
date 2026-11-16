import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_duplicate_completed_reconciliation_does_not_duplicate_audit(tmp_path):
    db=tmp_path/'ledger.sqlite3'
    store=CommandIdempotencyStore(db)
    try:
        store.claim('key-354','charge',{'amount':354},execution_id='exec-354')
        store.mark_unknown('key-354','provider timeout')
        first=store.reconcile_completed('key-354',{'accepted':True},evidence='receipt-354',execution_id='exec-354')
        count_before=store._connection.execute('SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?',('key-354',)).fetchone()[0]
        second=store.reconcile_completed('key-354',{'accepted':True},evidence='receipt-354',execution_id='exec-354')
        count_after=store._connection.execute('SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key=?',('key-354',)).fetchone()[0]
        assert second == first
        assert count_after == count_before == 1
    finally: store.close()
