from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_reconciled_not_executed_state_and_generation_survive_restart(tmp_path):
    db=tmp_path/'ledger.sqlite3'; s=CommandIdempotencyStore(db)
    s.claim('k370','charge',{'amount':370},execution_id='e370'); s.reserve_dispatch('k370')
    s.mark_unknown('k370','lost acknowledgement')
    expected=s.reconcile_not_executed('k370',evidence='provider lookup says absent',execution_id='e370'); s.close()
    s=CommandIdempotencyStore(db)
    try:
        actual=s.get('k370')
        assert actual == expected and actual.dispatch_started is False and actual.dispatch_generation == 1
        assert s.reserve_dispatch('k370') is True
        assert s.get('k370').dispatch_generation == 2
    finally: s.close()
