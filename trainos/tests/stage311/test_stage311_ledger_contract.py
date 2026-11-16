from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_required_text_identifiers_are_trimmed_consistently(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        claim = store.claim("  key-311  ", "  move  ", {"x": 1}, execution_id="  exec-311  ")
        assert claim.record.idempotency_key == "key-311"
        assert claim.record.command_name == "move"
        assert claim.record.execution_id == "exec-311"
        assert store.get("  key-311  ") == claim.record
    finally:
        store.close()
