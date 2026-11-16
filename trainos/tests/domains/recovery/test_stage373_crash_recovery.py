from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_completed_operation_result_is_durable_after_close_reopen(tmp_path):
    db=tmp_path/'ledger.sqlite3'; s=CommandIdempotencyStore(db)
    s.claim('k373','charge',{'amount':373},execution_id='e373')
    expected=s.complete('k373',{'status':'settled','receipt':'r373'},execution_id='e373'); s.close()
    s=CommandIdempotencyStore(db)
    try:
        actual=s.get('k373')
        assert actual == expected and actual.status is IdempotencyStatus.COMPLETED
        assert actual.result == {'receipt':'r373','status':'settled'}
        assert s.reserve_dispatch('k373') is False
    finally: s.close()
