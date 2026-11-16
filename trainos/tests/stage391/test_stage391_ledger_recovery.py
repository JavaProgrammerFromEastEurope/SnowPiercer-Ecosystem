from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_bad_fingerprint_is_reported_and_not_rewritten(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('k391','charge',{'amount':391})
        store._connection.execute("UPDATE command_idempotency SET fingerprint='bad' WHERE idempotency_key='k391'")
        before=store._connection.execute("SELECT fingerprint FROM command_idempotency WHERE idempotency_key='k391'").fetchone()[0]
        findings=store.check_integrity()
        after=store._connection.execute("SELECT fingerprint FROM command_idempotency WHERE idempotency_key='k391'").fetchone()[0]
        assert any('corrupt command idempotency fingerprint' in f for f in findings)
        assert before == after == 'bad'
    finally: store.close()
