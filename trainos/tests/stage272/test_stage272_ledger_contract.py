import math
import pytest
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


@pytest.mark.parametrize("payload", [{"value": math.nan}, {"value": math.inf}, {"value": -math.inf}])
def test_non_finite_payload_numbers_are_rejected_without_mutation(tmp_path, payload):
    store = CommandIdempotencyStore(tmp_path / "ledger.sqlite3")
    try:
        with pytest.raises(ValueError, match="payload must be JSON-serializable"):
            store.claim("key-272", "move", payload)
        assert store.get("key-272") is None
    finally:
        store.close()
