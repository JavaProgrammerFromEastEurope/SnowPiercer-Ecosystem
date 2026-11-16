from tests.ledger_backup_helpers import make_two_generation_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus

def test_unknown_record_and_multi_generation_audit_survive_reopen(tmp_path):
    backup = make_two_generation_backup(tmp_path)
    store = CommandIdempotencyStore(backup)
    record = store.get("key-1")
    rows = store._connection.execute("SELECT dispatch_generation FROM command_idempotency_reconciliation ORDER BY sequence").fetchall()
    store.close()
    assert record is not None
    assert record.dispatch_generation == 2
    assert [row["dispatch_generation"] for row in rows] == [1,2]
    assert CommandIdempotencyStore.validate_backup(backup) == ()
