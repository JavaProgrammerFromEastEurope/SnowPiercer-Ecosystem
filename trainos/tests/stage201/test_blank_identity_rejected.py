import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

@pytest.mark.parametrize("key,name", [("", "move"), ("   ", "move"), ("key-201", " ")])
def test_blank_identity_is_rejected_without_creating_record(tmp_path, key, name):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="must not be empty"):
            store.claim(key, name, {"x": 1})
        assert store.get("key-201") is None
    finally:
        store.close()
