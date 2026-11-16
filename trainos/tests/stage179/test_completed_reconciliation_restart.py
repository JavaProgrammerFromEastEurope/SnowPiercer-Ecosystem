from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore, IdempotencyStatus


def test_completed_reconciliation_survives_restart(tmp_path):
    path = tmp_path / "completed-restart.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("key-179", "set_speed", {"speed": 3}, execution_id="exec-179")
    store.reserve_dispatch("key-179")
    store.mark_unknown("key-179", "acknowledgement lost")
    evidence = "device audit says speed set to 3"
    store.reconcile_completed("key-179", {"speed": 3, "ok": True}, evidence=evidence, execution_id="exec-179")
    store.close()
    reopened = CommandIdempotencyStore(path)
    try:
        record = reopened.get("key-179")
        assert record.status is IdempotencyStatus.COMPLETED
        assert record.result == {"ok": True, "speed": 3}
        row = reopened._connection.execute(
            "SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key=?",
            ("key-179",),
        ).fetchone()
        assert tuple(row) == (evidence, "completed", 1)
        assert reopened.reserve_dispatch("key-179") is False
    finally:
        reopened.close()
