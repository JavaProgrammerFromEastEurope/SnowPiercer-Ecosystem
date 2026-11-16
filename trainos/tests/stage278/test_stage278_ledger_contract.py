from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_claim_normalizes_required_identity_text_without_duplicate_record(tmp_path):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        first = store.claim("  key-278  ", "  move  ", {"x": 1})
        second = store.claim("key-278", "move", {"x": 1})
        assert first.created is True
        assert second.created is False
        assert second.record.idempotency_key == "key-278"
        assert second.record.command_name == "move"
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        store.close()
