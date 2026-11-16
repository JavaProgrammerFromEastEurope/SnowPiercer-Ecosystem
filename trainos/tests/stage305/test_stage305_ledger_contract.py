import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

@pytest.mark.parametrize("result", [{"x": float("nan")}, {"x": float("inf")}, object()])
def test_invalid_completion_result_does_not_mutate_claim(tmp_path, result):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        store.claim("key-305", "move", {"x": 1}, execution_id="exec-305")
        before = store.get("key-305")
        with pytest.raises(ValueError, match="result must be JSON-serializable"):
            store.complete("key-305", result, execution_id="exec-305")
        assert store.get("key-305") == before
    finally:
        store.close()
