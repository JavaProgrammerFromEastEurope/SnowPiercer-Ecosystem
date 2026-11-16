from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_dispatch_reservation_is_durable_and_not_reissued_after_reopen(tmp_path):
    db=tmp_path/'ledger.sqlite3'; s=CommandIdempotencyStore(db)
    s.claim('k368','charge',{'amount':368},execution_id='e368')
    assert s.reserve_dispatch('k368') is True
    expected=s.get('k368'); s.close()
    s=CommandIdempotencyStore(db)
    try:
        assert s.get('k368') == expected
        assert s.reserve_dispatch('k368') is False
        assert s.get('k368').dispatch_generation == 1
    finally: s.close()
