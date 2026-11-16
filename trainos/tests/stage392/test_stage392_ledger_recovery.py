from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_bad_result_json_is_reported_without_mutation(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('k392','charge',{'amount':392})
        store.complete('k392', {'ok': True})
        store._connection.execute("UPDATE command_idempotency SET result_json='{' WHERE idempotency_key='k392'")
        before=store._connection.execute("SELECT result_json FROM command_idempotency WHERE idempotency_key='k392'").fetchone()[0]
        findings=store.check_integrity()
        after=store._connection.execute("SELECT result_json FROM command_idempotency WHERE idempotency_key='k392'").fetchone()[0]
        assert any('corrupt command idempotency record' in f for f in findings)
        assert before == after == '{'
    finally: store.close()
