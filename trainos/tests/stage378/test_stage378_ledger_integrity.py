from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_clean_ledger_reports_no_integrity_findings(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("k378", "charge", {"amount": 378}, execution_id="e378")
        assert store.check_integrity() == ()
    finally:
        store.close()
