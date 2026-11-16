from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_outcome_survives_restart_and_blocks_dispatch(tmp_path):
    db=tmp_path/'ledger.sqlite3'; s=CommandIdempotencyStore(db)
    s.claim('k369','charge',{'amount':369},execution_id='e369'); s.reserve_dispatch('k369')
    expected=s.mark_unknown('k369','process interrupted after dispatch'); s.close()
    s=CommandIdempotencyStore(db)
    try:
        actual=s.get('k369')
        assert actual == expected and actual.status is IdempotencyStatus.UNKNOWN
        assert s.reserve_dispatch('k369') is False
    finally: s.close()
