from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_repeated_equivalent_claim_returns_existing_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("key-308", "move", {"x": 1, "y": 2}, execution_id="exec-308")
        repeated = store.claim("key-308", "move", {"y": 2, "x": 1}, execution_id="exec-308")
        assert first.created is True
        assert repeated.created is False
        assert repeated.record == first.record
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        store.close()
