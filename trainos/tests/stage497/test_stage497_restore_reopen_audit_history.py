import shutil
from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_restore_reopen_preserves_audit_generations_and_claimed_state(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    restored = tmp_path / "restored.db"
    shutil.copy2(backup, restored)
    assert CommandIdempotencyStore.validate_backup(restored) == ()
    store = CommandIdempotencyStore(restored)
    record = store.get("key-1")
    assert record is not None
    assert record.status is IdempotencyStatus.CLAIMED
    assert record.dispatch_generation == 2
    rows = store._connection.execute(
        "SELECT dispatch_generation, decision FROM command_idempotency_reconciliation ORDER BY sequence"
    ).fetchall()
    assert [(row["dispatch_generation"], row["decision"]) for row in rows] == [
        (1, "not_executed"), (2, "not_executed")
    ]
    store.close()
    assert CommandIdempotencyStore.validate_backup(restored) == ()
