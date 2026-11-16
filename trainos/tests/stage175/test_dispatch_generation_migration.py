import hashlib
import json
import multiprocessing
import sqlite3

import pytest

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
    IdempotencyStatus,
)


def _fingerprint(name, payload):
    envelope = json.dumps(
        {"command_name": name, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(envelope.encode("utf-8")).hexdigest()


def _create_legacy_database(path):
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE command_idempotency (
            idempotency_key TEXT PRIMARY KEY,
            command_name TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('claimed', 'unknown', 'completed')),
            result_json TEXT,
            uncertainty_reason TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            execution_id TEXT,
            dispatch_started INTEGER NOT NULL DEFAULT 0 CHECK(dispatch_started IN (0, 1)),
            CHECK((status = 'completed' AND result_json IS NOT NULL AND uncertainty_reason IS NULL)
               OR (status = 'unknown' AND result_json IS NULL AND uncertainty_reason IS NOT NULL)
               OR (status = 'claimed' AND result_json IS NULL AND uncertainty_reason IS NULL))
        )"""
    )
    connection.execute(
        "INSERT INTO command_idempotency "
        "(idempotency_key, command_name, fingerprint, status, uncertainty_reason, execution_id, dispatch_started) "
        "VALUES (?, ?, ?, 'unknown', ?, ?, 1)",
        ("legacy-key", "set_route", _fingerprint("set_route", {"route": "R-7"}),
         "acknowledgement lost", "exec-legacy"),
    )
    connection.execute(
        """CREATE TABLE command_idempotency_reconciliation (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT NOT NULL,
            evidence TEXT NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            decision TEXT NOT NULL DEFAULT 'completed'
        )"""
    )
    connection.execute(
        "INSERT INTO command_idempotency_reconciliation(idempotency_key, evidence, decision) "
        "VALUES ('legacy-key', 'old controller receipt', 'not_executed')"
    )
    connection.commit()
    connection.close()


def _open_and_close(path, barrier, results):
    try:
        barrier.wait(timeout=10)
        store = CommandIdempotencyStore(path)
        record = store.get("legacy-key")
        results.put((record.dispatch_generation, record.dispatch_started, record.execution_id))
        store.close()
    except BaseException as exc:  # pragma: no cover - surfaced in parent assertion
        results.put(("ERROR", repr(exc), ""))


def test_legacy_migration_preserves_records_and_blocks_reuse_of_old_evidence(tmp_path):
    path = tmp_path / "legacy-generation.sqlite3"
    _create_legacy_database(path)

    store = CommandIdempotencyStore(path)
    try:
        record = store.get("legacy-key")
        assert record.status is IdempotencyStatus.UNKNOWN
        assert record.dispatch_started is True
        assert record.dispatch_generation == 1
        assert record.execution_id == "exec-legacy"

        # First successful reconciliation performs the legacy reconciliation-table migration.
        resolved = store.reconcile_not_executed(
            "legacy-key", evidence="new independently verified receipt", execution_id="exec-legacy"
        )
        assert resolved.status is IdempotencyStatus.CLAIMED
        assert resolved.dispatch_generation == 1
        history = store._connection.execute(
            "SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation "
            "WHERE idempotency_key='legacy-key' ORDER BY sequence"
        ).fetchall()
        assert [(row["evidence"], row["decision"], row["dispatch_generation"]) for row in history] == [
            ("old controller receipt", "not_executed", 0),
            ("new independently verified receipt", "not_executed", 1),
        ]
        assert store.reserve_dispatch("legacy-key") is True
        assert store.get("legacy-key").dispatch_generation == 2
        store.mark_unknown("legacy-key", "next attempt has no acknowledgement")
        with pytest.raises(IdempotencyConflict, match="predates a later dispatch"):
            store.reconcile_not_executed(
                "legacy-key", evidence="old controller receipt", execution_id="exec-legacy"
            )
    finally:
        store.close()


def test_concurrent_processes_migrate_legacy_schema_without_losing_generation(tmp_path):
    path = tmp_path / "legacy-concurrent-migration.sqlite3"
    _create_legacy_database(path)
    context = multiprocessing.get_context("spawn")
    workers = 4
    barrier = context.Barrier(workers)
    results = context.Queue()
    processes = [
        context.Process(target=_open_and_close, args=(str(path), barrier, results))
        for _ in range(workers)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
    try:
        assert all(not process.is_alive() for process in processes), "migration process hung"
        assert [process.exitcode for process in processes] == [0] * workers
        outcomes = [results.get(timeout=3) for _ in processes]
        assert outcomes == [(1, True, "exec-legacy")] * workers
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)

    reopened = CommandIdempotencyStore(path)
    try:
        record = reopened.get("legacy-key")
        assert record.dispatch_generation == 1
        assert record.dispatch_started is True
        columns = {row["name"] for row in reopened._connection.execute(
            "PRAGMA table_info(command_idempotency)"
        ).fetchall()}
        assert {"execution_id", "dispatch_started", "dispatch_generation"}.issubset(columns)
    finally:
        reopened.close()
