from tests.ledger_backup_helpers import make_multi_audit_backup
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_reopen_preserves_audit_sequence_and_decisions(tmp_path):
    backup = make_multi_audit_backup(tmp_path, count=2)
    before = CommandIdempotencyStore.validate_backup(backup)
    store = CommandIdempotencyStore(backup)
    rows = store._connection.execute("SELECT sequence,idempotency_key,decision,dispatch_generation FROM command_idempotency_reconciliation ORDER BY sequence").fetchall()
    store.close()
    assert before == ()
    assert [(r["sequence"],r["idempotency_key"],r["decision"],r["dispatch_generation"]) for r in rows] == [(1,"key-1","completed",0),(2,"key-2","completed",0)]
    assert CommandIdempotencyStore.validate_backup(backup) == ()
