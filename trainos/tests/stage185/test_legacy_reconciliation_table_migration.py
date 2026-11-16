import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore


def test_legacy_reconciliation_schema_is_upgraded_preserving_history(tmp_path):
    path = tmp_path / "legacy-audit.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("key-185", "inspect", {"target": "D"}, execution_id="exec-185")
    store.reserve_dispatch("key-185")
    store.mark_unknown("key-185", "lost ack")
    store.close()
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE command_idempotency_reconciliation (sequence INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL, evidence TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))) ")
    connection.execute("INSERT INTO command_idempotency_reconciliation(idempotency_key,evidence) VALUES('key-185','legacy receipt')")
    connection.commit(); connection.close()
    reopened = CommandIdempotencyStore(path)
    try:
        reopened.reconcile_not_executed("key-185", evidence="fresh receipt", execution_id="exec-185")
        columns = {r[1] for r in reopened._connection.execute("PRAGMA table_info(command_idempotency_reconciliation)")}
        assert {"decision", "dispatch_generation"}.issubset(columns)
        rows = reopened._connection.execute("SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation WHERE idempotency_key='key-185' ORDER BY sequence").fetchall()
        assert [tuple(r) for r in rows] == [("legacy receipt", "completed", 0), ("fresh receipt", "not_executed", 1)]
    finally:
        reopened.close()
