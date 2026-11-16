import hashlib
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def test_validation_does_not_change_database_bytes(tmp_path):
    db = tmp_path / "ledger.db"
    store = CommandIdempotencyStore(db)
    store.claim("k", "charge", {"cents": 10})
    store.mark_unknown("k", reason="timeout")
    store.reconcile_completed("k", {"ok": True}, evidence="provider-confirmed")
    store.close()
    before = digest(db)
    assert CommandIdempotencyStore.validate_backup(db) == ()
    assert digest(db) == before
