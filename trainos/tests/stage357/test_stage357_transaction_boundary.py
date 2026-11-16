from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_repeated_claim_preserves_existing_dispatch_reservation(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('key-357','charge',{'amount':357},execution_id='exec-357')
        assert store.reserve_dispatch('key-357') is True
        before=store.get('key-357')
        repeated=store.claim('key-357','charge',{'amount':357},execution_id='exec-357')
        assert repeated.created is False
        assert store.get('key-357') == before
        assert store.reserve_dispatch('key-357') is False
    finally: store.close()
