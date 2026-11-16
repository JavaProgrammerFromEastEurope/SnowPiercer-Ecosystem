import sqlite3
from kernel.command.execution.command_idempotency_store import CommandIdempotencyStore

def test_legacy_dispatch_reservation_gets_generation_one(tmp_path):
    path = tmp_path / 'legacy.sqlite3'; c = sqlite3.connect(path)
    c.execute("CREATE TABLE command_idempotency (idempotency_key TEXT PRIMARY KEY, command_name TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('claimed','unknown','completed')), result_json TEXT, uncertainty_reason TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), execution_id TEXT, dispatch_started INTEGER NOT NULL DEFAULT 0 CHECK(dispatch_started IN (0,1)), CHECK((status='completed' AND result_json IS NOT NULL AND uncertainty_reason IS NULL) OR (status='unknown' AND result_json IS NULL AND uncertainty_reason IS NOT NULL) OR (status='claimed' AND result_json IS NULL AND uncertainty_reason IS NULL)))")
    c.execute("INSERT INTO command_idempotency(idempotency_key,command_name,fingerprint,status,dispatch_started) VALUES ('legacy389','charge',?,'claimed',1)", ('b'*64,)); c.commit(); c.close()
    store=CommandIdempotencyStore(path)
    try:
        rec=store.get('legacy389'); assert rec.dispatch_started is True and rec.dispatch_generation == 1
    finally: store.close()
