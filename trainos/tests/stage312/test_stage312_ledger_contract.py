import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

@pytest.mark.parametrize("key,name", [("", "move"), ("   ", "move"), ("key-312", ""), ("key-312", "  ")])
def test_blank_key_or_command_name_is_rejected_before_mutation(tmp_path, key, name):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError):
            store.claim(key, name, {"x": 1}, execution_id="exec-312")
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 0
    finally:
        store.close()
