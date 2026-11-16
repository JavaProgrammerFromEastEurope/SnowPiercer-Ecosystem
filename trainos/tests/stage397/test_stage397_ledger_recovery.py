from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_integrity_diagnostics_do_not_mutate_corrupt_rows(tmp_path):
    store=CommandIdempotencyStore(tmp_path/'ledger.sqlite3')
    try:
        store.claim('k397','charge',{'amount':397})
        store._connection.execute("UPDATE command_idempotency SET fingerprint='damaged' WHERE idempotency_key='k397'")
        before=tuple(store._connection.execute("SELECT idempotency_key, fingerprint, status, result_json, uncertainty_reason, dispatch_generation FROM command_idempotency WHERE idempotency_key='k397'").fetchone())
        first=store.check_integrity()
        middle=tuple(store._connection.execute("SELECT idempotency_key, fingerprint, status, result_json, uncertainty_reason, dispatch_generation FROM command_idempotency WHERE idempotency_key='k397'").fetchone())
        second=store.check_integrity()
        after=tuple(store._connection.execute("SELECT idempotency_key, fingerprint, status, result_json, uncertainty_reason, dispatch_generation FROM command_idempotency WHERE idempotency_key='k397'").fetchone())
        assert first == second and first and before == middle == after
    finally: store.close()
