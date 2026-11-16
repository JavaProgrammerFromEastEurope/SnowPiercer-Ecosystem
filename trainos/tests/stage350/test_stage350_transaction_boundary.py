from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_identical_repeated_claim_returns_existing_record(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        first=store.claim('key-350','charge',{'amount':350},execution_id='exec-350')
        second=store.claim('key-350','charge',{'amount':350},execution_id='exec-350')
        assert first.created is True
        assert second.created is False
        assert second.record == first.record
    finally: store.close()
