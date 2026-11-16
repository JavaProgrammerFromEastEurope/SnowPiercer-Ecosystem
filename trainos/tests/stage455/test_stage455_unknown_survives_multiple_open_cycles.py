from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def make_store(tmp_path):
    return CommandIdempotencyStore(tmp_path / "ledger.db")

def test_unknown_survives_multiple_open_cycles(tmp_path):
    path = tmp_path / "ledger.db"; store = CommandIdempotencyStore(path)
    store.claim("key", "cmd", {"v": 1}); store.mark_unknown("key", reason="timeout"); store.close()
    for _ in range(3):
        reopened = CommandIdempotencyStore(path)
        try:
            record = reopened.get("key")
            assert record.status is IdempotencyStatus.UNKNOWN
            assert reopened.claim("key", "cmd", {"v": 1}).created is False
        finally: reopened.close()
