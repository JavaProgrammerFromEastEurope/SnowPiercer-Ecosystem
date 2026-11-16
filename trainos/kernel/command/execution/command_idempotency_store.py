from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any


class IdempotencyConflict(ValueError):
    """An idempotency key was reused for a different command or result."""


class IdempotencyStatus(str, Enum):
    CLAIMED = "claimed"
    UNKNOWN = "unknown"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    idempotency_key: str
    command_name: str
    fingerprint: str
    status: IdempotencyStatus
    result: Any | None
    uncertainty_reason: str | None
    execution_id: str | None = None
    dispatch_started: bool = False
    dispatch_generation: int = 0


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    record: IdempotencyRecord
    created: bool


class CommandIdempotencyStore:
    """Durable idempotency ledger for commands crossing an external boundary.

    Repeated claims with the same key and canonical command payload return the
    existing record; they never authorize another external execution. Reusing a
    key for a different command is rejected. UNKNOWN is intentionally not
    automatically retried: an external observer must reconcile the outcome.

    This SQLite ledger is application storage, not a distributed consensus
    mechanism or a safety-certified command executor.
    """

    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path) -> None:
        if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
            raise ValueError("database_path must not be empty")
        self._database_path = str(database_path)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            self._database_path, timeout=30, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        try:
            schema_version = int(
                self._connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if schema_version < 0:
                raise RuntimeError(
                    f"invalid ledger schema version {schema_version}; versions cannot be negative"
                )
            if schema_version > self.SCHEMA_VERSION:
                raise RuntimeError(
                    f"unsupported ledger schema version {schema_version}; "
                    f"maximum supported version is {self.SCHEMA_VERSION}"
                )
            with self._lock, self._connection:
                # Start the transaction before any DDL. SQLite's connection
                # context alone does not necessarily begin a transaction before
                # ALTER TABLE / CREATE INDEX, so a later migration failure could
                # otherwise leave a partially upgraded schema behind.
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute("PRAGMA busy_timeout = 30000")
                self._connection.execute(
                    """CREATE TABLE IF NOT EXISTS command_idempotency (
                        idempotency_key TEXT PRIMARY KEY,
                        command_name TEXT NOT NULL,
                        fingerprint TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('claimed', 'unknown', 'completed')),
                        result_json TEXT,
                        uncertainty_reason TEXT,
                        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                        dispatch_generation INTEGER NOT NULL DEFAULT 0 CHECK(dispatch_generation >= 0),
                        CHECK((status = 'completed' AND result_json IS NOT NULL AND uncertainty_reason IS NULL)
                           OR (status = 'unknown' AND result_json IS NULL AND uncertainty_reason IS NOT NULL)
                           OR (status = 'claimed' AND result_json IS NULL AND uncertainty_reason IS NULL))
                    )"""
                )
                columns = {
                    row["name"]
                    for row in self._connection.execute(
                        "PRAGMA table_info(command_idempotency)"
                    ).fetchall()
                }
                if "execution_id" not in columns:
                    # Multiple processes may open a legacy database simultaneously.
                    # Another initializer can add the column after our PRAGMA read
                    # but before ALTER TABLE; treat that exact race as successful
                    # migration only after verifying the column now exists.
                    try:
                        self._connection.execute(
                            "ALTER TABLE command_idempotency ADD COLUMN execution_id TEXT"
                        )
                    except sqlite3.OperationalError as exc:
                        refreshed = {
                            row["name"]
                            for row in self._connection.execute(
                                "PRAGMA table_info(command_idempotency)"
                            ).fetchall()
                        }
                        if (
                            "execution_id" not in refreshed
                            or "duplicate column name" not in str(exc).lower()
                        ):
                            raise
                columns = {
                    row["name"]
                    for row in self._connection.execute(
                        "PRAGMA table_info(command_idempotency)"
                    ).fetchall()
                }
                if "dispatch_started" not in columns:
                    try:
                        self._connection.execute(
                            "ALTER TABLE command_idempotency ADD COLUMN dispatch_started INTEGER NOT NULL DEFAULT 0 "
                            "CHECK(dispatch_started IN (0, 1))"
                        )
                    except sqlite3.OperationalError as exc:
                        refreshed = {
                            row["name"]
                            for row in self._connection.execute(
                                "PRAGMA table_info(command_idempotency)"
                            ).fetchall()
                        }
                        if (
                            "dispatch_started" not in refreshed
                            or "duplicate column name" not in str(exc).lower()
                        ):
                            raise
                columns = {
                    row["name"]
                    for row in self._connection.execute(
                        "PRAGMA table_info(command_idempotency)"
                    ).fetchall()
                }
                if "dispatch_generation" not in columns:
                    try:
                        self._connection.execute(
                            "ALTER TABLE command_idempotency ADD COLUMN dispatch_generation INTEGER NOT NULL DEFAULT 0 "
                            "CHECK(dispatch_generation >= 0)"
                        )
                    except sqlite3.OperationalError as exc:
                        refreshed = {
                            row["name"]
                            for row in self._connection.execute(
                                "PRAGMA table_info(command_idempotency)"
                            ).fetchall()
                        }
                        if (
                            "dispatch_generation" not in refreshed
                            or "duplicate column name" not in str(exc).lower()
                        ):
                            raise
                # Always backfill legacy reservations, even if another process added
                # the column between our schema inspection and ALTER TABLE. Keeping
                # this outside the conditional closes that migration race.
                self._connection.execute(
                    "UPDATE command_idempotency SET dispatch_generation=1 "
                    "WHERE dispatch_started=1 AND dispatch_generation=0"
                )
                self._connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_command_idempotency_execution_id "
                    "ON command_idempotency(execution_id) WHERE execution_id IS NOT NULL"
                )

                # Do not stamp a database as current until the actual structure has
                # been checked. Raising here rolls back table alterations and the
                # user_version update together through the connection context.
                required_columns = {
                    "idempotency_key",
                    "command_name",
                    "fingerprint",
                    "status",
                    "result_json",
                    "uncertainty_reason",
                    "created_at",
                    "updated_at",
                    "execution_id",
                    "dispatch_started",
                    "dispatch_generation",
                }
                actual_columns = {
                    row["name"]
                    for row in self._connection.execute(
                        "PRAGMA table_info(command_idempotency)"
                    ).fetchall()
                }
                missing_columns = sorted(required_columns - actual_columns)
                if missing_columns:
                    raise RuntimeError(
                        "ledger schema is missing required columns: "
                        + ", ".join(missing_columns)
                    )
                index_info = self._connection.execute(
                    "PRAGMA index_list(command_idempotency)"
                ).fetchall()
                execution_index = next(
                    (
                        row
                        for row in index_info
                        if row["name"] == "idx_command_idempotency_execution_id"
                    ),
                    None,
                )
                if (
                    execution_index is None
                    or execution_index["unique"] != 1
                    or execution_index["partial"] != 1
                ):
                    raise RuntimeError(
                        "ledger schema execution_id index is missing or invalid"
                    )

                self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        except BaseException:
            self._connection.close()
            raise

    @property
    def database_path(self) -> str:
        return self._database_path

    @staticmethod
    def _required_text(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must not be empty")
        return value.strip()

    @staticmethod
    def _canonical_json(value: Any, name: str) -> str:
        try:
            return json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be JSON-serializable") from exc

    @classmethod
    def _fingerprint(cls, command_name: str, payload: Any) -> str:
        envelope = cls._canonical_json(
            {"command_name": command_name, "payload": payload}, "command"
        )
        return hashlib.sha256(envelope.encode("utf-8")).hexdigest()

    @staticmethod
    def _record(row: sqlite3.Row) -> IdempotencyRecord:
        try:
            status = IdempotencyStatus(row["status"])
            result = (
                json.loads(row["result_json"])
                if row["result_json"] is not None
                else None
            )
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("corrupt command idempotency record") from exc
        if not row["idempotency_key"].strip() or not row["command_name"].strip():
            raise RuntimeError("corrupt command idempotency identity")
        if len(row["fingerprint"]) != 64 or any(
            c not in "0123456789abcdef" for c in row["fingerprint"]
        ):
            raise RuntimeError("corrupt command idempotency fingerprint")
        if status is IdempotencyStatus.CLAIMED and (
            result is not None or row["uncertainty_reason"] is not None
        ):
            raise RuntimeError("corrupt claimed command idempotency record")
        if status is IdempotencyStatus.UNKNOWN and (
            result is not None or not row["uncertainty_reason"]
        ):
            raise RuntimeError("corrupt unknown command idempotency record")
        if status is IdempotencyStatus.COMPLETED and (
            row["result_json"] is None or row["uncertainty_reason"] is not None
        ):
            raise RuntimeError("corrupt completed command idempotency record")
        execution_id = row["execution_id"] if "execution_id" in row.keys() else None
        if execution_id is not None and (
            not isinstance(execution_id, str) or not execution_id.strip()
        ):
            raise RuntimeError("corrupt command idempotency execution identity")
        dispatch_started = (
            bool(row["dispatch_started"]) if "dispatch_started" in row.keys() else False
        )
        if "dispatch_started" in row.keys() and row["dispatch_started"] not in (0, 1):
            raise RuntimeError("corrupt command idempotency dispatch reservation")
        dispatch_generation = (
            row["dispatch_generation"] if "dispatch_generation" in row.keys() else 0
        )
        if not isinstance(dispatch_generation, int) or dispatch_generation < 0:
            raise RuntimeError("corrupt command idempotency dispatch generation")
        return IdempotencyRecord(
            row["idempotency_key"],
            row["command_name"],
            row["fingerprint"],
            status,
            result,
            row["uncertainty_reason"],
            execution_id,
            dispatch_started,
            dispatch_generation,
        )

    def claim(
        self,
        idempotency_key: str,
        command_name: str,
        payload: Any,
        *,
        execution_id: str | None = None,
    ) -> IdempotencyClaim:
        key = self._required_text(idempotency_key, "idempotency_key")
        name = self._required_text(command_name, "command_name")
        bound_execution_id = (
            self._required_text(execution_id, "execution_id")
            if execution_id is not None
            else None
        )
        payload_json = self._canonical_json(payload, "payload")
        normalized_payload = json.loads(payload_json)
        fingerprint = self._fingerprint(name, normalized_payload)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if row is not None:
                    record = self._record(row)
                    if record.command_name != name or record.fingerprint != fingerprint:
                        raise IdempotencyConflict(
                            "idempotency key reused for a different command"
                        )
                    if bound_execution_id is not None and record.execution_id is None:
                        raise IdempotencyConflict(
                            "cannot bind execution_id after command claim"
                        )
                    if (
                        bound_execution_id is not None
                        and record.execution_id != bound_execution_id
                    ):
                        raise IdempotencyConflict(
                            "idempotency key bound to a different execution"
                        )
                    self._connection.commit()
                    return IdempotencyClaim(record, False)
                try:
                    self._connection.execute(
                        "INSERT INTO command_idempotency(idempotency_key, command_name, fingerprint, status, execution_id) "
                        "VALUES (?, ?, ?, 'claimed', ?)",
                        (key, name, fingerprint, bound_execution_id),
                    )
                except sqlite3.IntegrityError as exc:
                    if bound_execution_id is not None:
                        raise IdempotencyConflict(
                            "execution_id already bound to another idempotency key"
                        ) from exc
                    raise
                row = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                record = self._record(row)
                self._connection.commit()
                return IdempotencyClaim(record, True)
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise

    def get(self, idempotency_key: str) -> IdempotencyRecord | None:
        key = self._required_text(idempotency_key, "idempotency_key")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM command_idempotency WHERE idempotency_key = ?", (key,)
            ).fetchone()
        return self._record(row) if row is not None else None

    def reserve_dispatch(self, idempotency_key: str) -> bool:
        """Atomically reserve the single dispatch attempt across store instances/processes.

        A reservation is durable and intentionally not cleared automatically. If
        the caller crashes or loses the external acknowledgement, explicit
        reconciliation is required rather than an unsafe second dispatch.
        """
        key = self._required_text(idempotency_key, "idempotency_key")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT status, execution_id, dispatch_started FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    raise ValueError("unknown idempotency key")
                if (
                    row["status"] != IdempotencyStatus.CLAIMED.value
                    or not row["execution_id"]
                ):
                    self._connection.commit()
                    return False
                if row["dispatch_started"]:
                    self._connection.commit()
                    return False
                cursor = self._connection.execute(
                    "UPDATE command_idempotency SET dispatch_started = 1, dispatch_generation=dispatch_generation+1, "
                    "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                    "WHERE idempotency_key = ? AND status = 'claimed' AND dispatch_started = 0",
                    (key,),
                )
                reserved = cursor.rowcount == 1
                self._connection.commit()
                return reserved
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise

    def mark_unknown(self, idempotency_key: str, reason: str) -> IdempotencyRecord:
        key = self._required_text(idempotency_key, "idempotency_key")
        why = self._required_text(reason, "reason")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    raise ValueError("unknown idempotency key")
                record = self._record(row)
                if record.status is IdempotencyStatus.UNKNOWN:
                    if record.uncertainty_reason != why:
                        raise IdempotencyConflict("conflicting unknown-outcome reason")
                    self._connection.commit()
                    return record
                if record.status is not IdempotencyStatus.CLAIMED:
                    raise ValueError("only claimed commands can become unknown")
                self._connection.execute(
                    "UPDATE command_idempotency SET status='unknown', uncertainty_reason=?, "
                    "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE idempotency_key=?",
                    (why, key),
                )
                updated = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                result = self._record(updated)
                self._connection.commit()
                return result
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise

    def complete(
        self, idempotency_key: str, result: Any, *, execution_id: str | None = None
    ) -> IdempotencyRecord:
        key = self._required_text(idempotency_key, "idempotency_key")
        supplied_execution_id = (
            self._required_text(execution_id, "execution_id")
            if execution_id is not None
            else None
        )
        result_json = self._canonical_json(result, "result")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    raise ValueError("unknown idempotency key")
                record = self._record(row)
                self._validate_execution_binding(record, supplied_execution_id)
                if record.status is IdempotencyStatus.COMPLETED:
                    if (
                        self._canonical_json(record.result, "stored result")
                        != result_json
                    ):
                        raise IdempotencyConflict(
                            "conflicting duplicate command result"
                        )
                    self._connection.commit()
                    return record
                if record.status is not IdempotencyStatus.CLAIMED:
                    raise ValueError(
                        "unknown command outcome must be reconciled before completion"
                    )
                self._connection.execute(
                    "UPDATE command_idempotency SET status='completed', result_json=?, "
                    "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE idempotency_key=?",
                    (result_json, key),
                )
                updated = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                result_record = self._record(updated)
                self._connection.commit()
                return result_record
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise

    def _ensure_reconciliation_table(self) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS command_idempotency_reconciliation ("
            "sequence INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL, "
            "evidence TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT "
            "(strftime('%Y-%m-%dT%H:%M:%fZ','now')), decision TEXT NOT NULL DEFAULT 'completed', "
            "dispatch_generation INTEGER NOT NULL DEFAULT 0 CHECK(dispatch_generation >= 0))"
        )
        columns = {
            row["name"]
            for row in self._connection.execute(
                "PRAGMA table_info(command_idempotency_reconciliation)"
            ).fetchall()
        }
        if "decision" not in columns:
            self._connection.execute(
                "ALTER TABLE command_idempotency_reconciliation ADD COLUMN decision TEXT NOT NULL DEFAULT 'completed'"
            )
        if "dispatch_generation" not in columns:
            self._connection.execute(
                "ALTER TABLE command_idempotency_reconciliation ADD COLUMN dispatch_generation INTEGER NOT NULL DEFAULT 0 "
                "CHECK(dispatch_generation >= 0)"
            )

    def reconcile_not_executed(
        self, idempotency_key: str, *, evidence: str, execution_id: str | None = None
    ) -> IdempotencyRecord:
        """Resolve UNKNOWN as not executed only with explicit durable evidence.

        This authorizes a fresh reservation only after evidence is supplied; a
        timeout, missing audit row, or restart alone is never proof of non-execution.
        """
        key = self._required_text(idempotency_key, "idempotency_key")
        supplied_execution_id = (
            self._required_text(execution_id, "execution_id")
            if execution_id is not None
            else None
        )
        proof = self._required_text(evidence, "evidence")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._ensure_reconciliation_table()
                row = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    raise ValueError("unknown idempotency key")
                record = self._record(row)
                self._validate_execution_binding(record, supplied_execution_id)
                latest = self._connection.execute(
                    "SELECT decision, evidence, dispatch_generation FROM command_idempotency_reconciliation "
                    "WHERE idempotency_key=? ORDER BY sequence DESC LIMIT 1",
                    (key,),
                ).fetchone()
                prior_evidence = self._connection.execute(
                    "SELECT 1 FROM command_idempotency_reconciliation "
                    "WHERE idempotency_key=? AND decision='not_executed' AND evidence=? "
                    "AND dispatch_generation < ? LIMIT 1",
                    (key, proof, record.dispatch_generation),
                ).fetchone()
                if prior_evidence is not None:
                    raise IdempotencyConflict(
                        "evidence predates a later dispatch attempt and cannot be reused"
                    )
                if record.status is IdempotencyStatus.CLAIMED:
                    if (
                        latest is not None
                        and latest["decision"] == "not_executed"
                        and latest["dispatch_generation"] == record.dispatch_generation
                    ):
                        if latest["evidence"] != proof:
                            raise IdempotencyConflict(
                                "conflicting evidence for not-executed reconciliation"
                            )
                        if not record.dispatch_started:
                            self._connection.commit()
                            return record
                    raise ValueError(
                        "only unknown outcomes can be reconciled as not executed"
                    )
                if record.status is not IdempotencyStatus.UNKNOWN:
                    raise ValueError(
                        "only unknown outcomes can be reconciled as not executed"
                    )
                if (
                    latest is not None
                    and latest["decision"] == "not_executed"
                    and latest["dispatch_generation"] == record.dispatch_generation
                    and latest["evidence"] != proof
                ):
                    raise IdempotencyConflict(
                        "conflicting evidence for not-executed reconciliation"
                    )
                self._connection.execute(
                    "UPDATE command_idempotency SET status='claimed', uncertainty_reason=NULL, dispatch_started=0, "
                    "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE idempotency_key=?",
                    (key,),
                )
                self._connection.execute(
                    "INSERT INTO command_idempotency_reconciliation "
                    "(idempotency_key, evidence, decision, dispatch_generation) "
                    "VALUES (?, ?, 'not_executed', ?)",
                    (key, proof, record.dispatch_generation),
                )
                updated = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key=?", (key,)
                ).fetchone()
                result = self._record(updated)
                self._connection.commit()
                return result
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise

    def reconcile_completed(
        self,
        idempotency_key: str,
        result: Any,
        *,
        evidence: str,
        execution_id: str | None = None,
    ) -> IdempotencyRecord:
        """Resolve an UNKNOWN outcome only with explicit, non-empty external evidence."""
        key = self._required_text(idempotency_key, "idempotency_key")
        supplied_execution_id = (
            self._required_text(execution_id, "execution_id")
            if execution_id is not None
            else None
        )
        proof = self._required_text(evidence, "evidence")
        result_json = self._canonical_json(result, "result")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    raise ValueError("unknown idempotency key")
                record = self._record(row)
                self._validate_execution_binding(record, supplied_execution_id)
                if record.status is IdempotencyStatus.COMPLETED:
                    if (
                        self._canonical_json(record.result, "stored result")
                        != result_json
                    ):
                        raise IdempotencyConflict(
                            "conflicting duplicate command result"
                        )
                    self._connection.commit()
                    return record
                if record.status is not IdempotencyStatus.UNKNOWN:
                    raise ValueError("only unknown outcomes can be reconciled")
                self._connection.execute(
                    "UPDATE command_idempotency SET status='completed', result_json=?, uncertainty_reason=NULL, "
                    "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE idempotency_key=?",
                    (result_json, key),
                )
                updated = self._connection.execute(
                    "SELECT * FROM command_idempotency WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()
                completed = self._record(updated)
                # Evidence is required at the API boundary; keep a durable audit entry too.
                self._ensure_reconciliation_table()
                self._connection.execute(
                    "INSERT INTO command_idempotency_reconciliation(idempotency_key, evidence, decision, dispatch_generation) "
                    "VALUES (?, ?, 'completed', ?)",
                    (key, proof, record.dispatch_generation),
                )
                self._connection.commit()
                return completed
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise

    @staticmethod
    def _validate_execution_binding(
        record: IdempotencyRecord, supplied_execution_id: str | None
    ) -> None:
        if record.execution_id is not None:
            if supplied_execution_id is None:
                raise IdempotencyConflict(
                    "bound command requires matching execution_id"
                )
            if supplied_execution_id != record.execution_id:
                raise IdempotencyConflict(
                    "execution_id does not match idempotency record"
                )
        elif supplied_execution_id is not None:
            raise IdempotencyConflict("cannot bind execution_id after command claim")

    def count_execution_bindings(self, execution_id: str) -> int:
        """Count ledger records bound to an execution ID for integrity checks.

        The unique index prevents duplicates during normal operation. Counting
        at the diagnostic boundary also detects a damaged/restored database in
        which that index has been lost or bypassed.
        """
        bound_execution_id = self._required_text(execution_id, "execution_id")
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) FROM command_idempotency WHERE execution_id = ?",
                (bound_execution_id,),
            ).fetchone()
        return int(row[0])

    def check_integrity(self) -> tuple[str, ...]:
        """Return durable-ledger integrity findings without mutating the database.

        An empty tuple means SQLite's structural check and the ledger's
        application-level checks passed. Findings are diagnostic only; this
        method never repairs or rewrites records automatically.
        """
        findings: list[str] = []
        with self._lock:
            try:
                sqlite_rows = self._connection.execute(
                    "PRAGMA integrity_check"
                ).fetchall()
                for row in sqlite_rows:
                    message = str(row[0])
                    if message.lower() != "ok":
                        findings.append(f"sqlite: {message}")
            except sqlite3.DatabaseError as exc:
                return (f"sqlite: integrity check failed: {exc}",)

            try:
                records = self._connection.execute(
                    "SELECT * FROM command_idempotency"
                ).fetchall()
            except sqlite3.DatabaseError as exc:
                return tuple(findings + [f"ledger: cannot read command records: {exc}"])

            records_by_key: dict[str, IdempotencyRecord] = {}
            for row in records:
                key = row["idempotency_key"]
                try:
                    record = self._record(row)
                    records_by_key[key] = record
                except (RuntimeError, ValueError, TypeError, KeyError) as exc:
                    findings.append(f"record {key!r}: {exc}")

            index_rows = self._connection.execute(
                "PRAGMA index_list(command_idempotency)"
            ).fetchall()
            execution_index = next(
                (
                    row
                    for row in index_rows
                    if row["name"] == "idx_command_idempotency_execution_id"
                ),
                None,
            )
            if execution_index is None:
                findings.append("schema: execution_id uniqueness index is missing")
            else:
                if int(execution_index["unique"]) != 1:
                    findings.append("schema: execution_id index is not unique")
                if int(execution_index["partial"]) != 1:
                    findings.append("schema: execution_id index is not partial")
                index_columns = [
                    row["name"]
                    for row in self._connection.execute(
                        "PRAGMA index_info(idx_command_idempotency_execution_id)"
                    ).fetchall()
                ]
                if index_columns != ["execution_id"]:
                    findings.append("schema: execution_id index has unexpected columns")
            duplicate_ids = self._connection.execute(
                "SELECT execution_id FROM command_idempotency WHERE execution_id IS NOT NULL "
                "GROUP BY execution_id HAVING COUNT(*) > 1"
            ).fetchall()
            for row in duplicate_ids:
                findings.append(
                    f"execution_id {row['execution_id']!r}: bound to multiple records"
                )

            tables = {
                row["name"]
                for row in self._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "command_idempotency_reconciliation" in tables:
                try:
                    audits = self._connection.execute(
                        "SELECT sequence, idempotency_key, evidence, decision, dispatch_generation "
                        "FROM command_idempotency_reconciliation ORDER BY sequence"
                    ).fetchall()
                except sqlite3.DatabaseError as exc:
                    findings.append(f"audit: cannot read reconciliation records: {exc}")
                    audits = []
                for audit in audits:
                    key = audit["idempotency_key"]
                    if key not in records_by_key:
                        findings.append(
                            f"audit {audit['sequence']}: orphan idempotency key {key!r}"
                        )
                        continue
                    if (
                        not isinstance(audit["evidence"], str)
                        or not audit["evidence"].strip()
                    ):
                        findings.append(f"audit {audit['sequence']}: empty evidence")
                    if audit["decision"] not in ("completed", "not_executed"):
                        findings.append(
                            f"audit {audit['sequence']}: invalid decision {audit['decision']!r}"
                        )
                    generation = audit["dispatch_generation"]
                    record = records_by_key[key]
                    if (
                        not isinstance(generation, int)
                        or generation < 0
                        or generation > record.dispatch_generation
                    ):
                        findings.append(
                            f"audit {audit['sequence']}: invalid dispatch generation"
                        )
                    if (
                        audit["decision"] == "completed"
                        and record.status is not IdempotencyStatus.COMPLETED
                    ):
                        findings.append(
                            f"audit {audit['sequence']}: completed decision has non-completed record"
                        )
        return tuple(findings)

    @classmethod
    def validate_backup(cls, backup_path: str | Path) -> tuple[str, ...]:
        """Validate a file-backed ledger snapshot without mutating it.

        An empty tuple means the exercised SQLite, schema-version, required-column,
        execution-index, and record-decoding checks passed. This is a local
        acceptance check, not a cryptographic authenticity or disaster-recovery guarantee.
        """
        if not isinstance(backup_path, (str, Path)) or not str(backup_path).strip():
            raise ValueError("backup_path must not be empty")
        path = Path(backup_path).expanduser().resolve()
        if not path.is_file():
            return ("backup: file does not exist",)
        uri = path.as_uri() + "?mode=ro"
        findings: list[str] = []
        connection = sqlite3.connect(uri, uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            # Keep every validation query on one read snapshot. Without an explicit
            # transaction, a concurrent writer could change audit rows between the
            # integrity, schema, and cross-record checks.
            connection.execute("BEGIN")
            integrity = connection.execute("PRAGMA integrity_check").fetchall()
            if not integrity or any(str(row[0]).lower() != "ok" for row in integrity):
                findings.extend(
                    f"sqlite: {row[0]}"
                    for row in integrity
                    if str(row[0]).lower() != "ok"
                )
                if not findings:
                    findings.append("sqlite: integrity check returned no result")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version != cls.SCHEMA_VERSION:
                findings.append(
                    f"schema: expected version {cls.SCHEMA_VERSION}, found {version}"
                )
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "command_idempotency" not in tables:
                return tuple(
                    findings + ["schema: command_idempotency table is missing"]
                )
            required = {
                "idempotency_key",
                "command_name",
                "fingerprint",
                "status",
                "result_json",
                "uncertainty_reason",
                "created_at",
                "updated_at",
                "execution_id",
                "dispatch_started",
                "dispatch_generation",
            }
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(command_idempotency)"
                ).fetchall()
            }
            missing = sorted(required - columns)
            if missing:
                findings.append("schema: missing columns: " + ", ".join(missing))
                return tuple(findings)
            indexes = connection.execute(
                "PRAGMA index_list(command_idempotency)"
            ).fetchall()
            index = next(
                (
                    row
                    for row in indexes
                    if row["name"] == "idx_command_idempotency_execution_id"
                ),
                None,
            )
            if index is None:
                findings.append("schema: execution_id uniqueness index is missing")
            else:
                if int(index["unique"]) != 1 or int(index["partial"]) != 1:
                    findings.append("schema: execution_id index definition is invalid")
                cols = [
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA index_info(idx_command_idempotency_execution_id)"
                    ).fetchall()
                ]
                if cols != ["execution_id"]:
                    findings.append("schema: execution_id index columns are invalid")
            records_by_key: dict[str, IdempotencyRecord] = {}
            try:
                for row in connection.execute(
                    "SELECT * FROM command_idempotency"
                ).fetchall():
                    try:
                        record = cls._record(row)
                        records_by_key[record.idempotency_key] = record
                    except (RuntimeError, ValueError, TypeError, KeyError) as exc:
                        findings.append(f"record {row['idempotency_key']!r}: {exc}")
            except sqlite3.DatabaseError as exc:
                findings.append(f"ledger: cannot read records: {exc}")

            # If a snapshot contains reconciliation history, validate its structure
            # and cross-record references too. This is read-only and deliberately
            # does not attempt to repair audit data during backup acceptance.
            if "command_idempotency_reconciliation" in tables:
                audit_required = {
                    "sequence",
                    "idempotency_key",
                    "evidence",
                    "recorded_at",
                    "decision",
                    "dispatch_generation",
                }
                audit_columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(command_idempotency_reconciliation)"
                    ).fetchall()
                }
                missing_audit = sorted(audit_required - audit_columns)
                if missing_audit:
                    findings.append(
                        "audit: missing columns: " + ", ".join(missing_audit)
                    )
                else:
                    try:
                        audit_info = connection.execute(
                            "PRAGMA table_info(command_idempotency_reconciliation)"
                        ).fetchall()
                        audit_schema = {row["name"]: row for row in audit_info}
                        sequence_info = audit_schema.get("sequence")
                        if sequence_info is None or int(sequence_info["pk"]) != 1:
                            findings.append("audit: sequence must be the primary key")
                        expected_audit_types = {
                            "sequence": "INTEGER",
                            "idempotency_key": "TEXT",
                            "evidence": "TEXT",
                            "recorded_at": "TEXT",
                            "decision": "TEXT",
                            "dispatch_generation": "INTEGER",
                        }
                        for column_name, expected_type in expected_audit_types.items():
                            column = audit_schema.get(column_name)
                            if (
                                column is not None
                                and str(column["type"]).strip().upper() != expected_type
                            ):
                                findings.append(
                                    f"audit: column {column_name} must have declared type {expected_type}"
                                )
                            if (
                                column_name != "sequence"
                                and column is not None
                                and int(column["notnull"]) != 1
                            ):
                                findings.append(
                                    f"audit: column {column_name} must be NOT NULL"
                                )
                        audits = connection.execute(
                            "SELECT sequence, idempotency_key, evidence, recorded_at, decision, dispatch_generation "
                            "FROM command_idempotency_reconciliation ORDER BY sequence"
                        ).fetchall()
                        previous_sequence = 0
                        previous_timestamp = None
                        seen_audit_events: set[tuple[str, int, str, str]] = set()
                        last_generation_by_key: dict[str, int] = {}
                        not_executed_evidence_generation: dict[tuple[str, str], int] = (
                            {}
                        )
                        decision_by_key_generation: dict[tuple[str, int], str] = {}
                        latest_audit_generation_by_key: dict[str, int] = {}
                        for audit in audits:
                            sequence = audit["sequence"]
                            if (
                                not isinstance(sequence, int)
                                or sequence <= previous_sequence
                            ):
                                findings.append(
                                    f"audit {sequence!r}: invalid or non-monotonic sequence"
                                )
                            elif sequence != previous_sequence + 1:
                                findings.append(
                                    f"audit {sequence!r}: sequence gap; expected {previous_sequence + 1}"
                                )
                                previous_sequence = sequence
                            else:
                                previous_sequence = sequence
                            if (
                                not isinstance(audit["idempotency_key"], str)
                                or not audit["idempotency_key"].strip()
                            ):
                                findings.append(
                                    f"audit {sequence}: idempotency_key must be non-empty text"
                                )
                            if (
                                not isinstance(audit["evidence"], str)
                                or not audit["evidence"].strip()
                            ):
                                findings.append(
                                    f"audit {sequence}: evidence must be non-empty text"
                                )
                            if not isinstance(audit["decision"], str):
                                findings.append(
                                    f"audit {sequence}: decision must be text"
                                )
                            if (
                                not isinstance(audit["dispatch_generation"], int)
                                or audit["dispatch_generation"] < 0
                            ):
                                findings.append(
                                    f"audit {sequence}: dispatch_generation must be a non-negative integer"
                                )
                            recorded_at = audit["recorded_at"]
                            parsed_utc = None
                            if (
                                not isinstance(recorded_at, str)
                                or not recorded_at.strip()
                            ):
                                findings.append(
                                    f"audit {sequence}: empty recorded_at timestamp"
                                )
                            else:
                                # Require ISO-8601 with an explicit timezone and compare
                                # instants in UTC, not their lexical representation.
                                try:
                                    parsed_timestamp = datetime.fromisoformat(
                                        recorded_at[:-1] + "+00:00"
                                        if recorded_at.endswith("Z")
                                        else recorded_at
                                    )
                                    if (
                                        parsed_timestamp.tzinfo is None
                                        or parsed_timestamp.utcoffset() is None
                                    ):
                                        findings.append(
                                            f"audit {sequence}: recorded_at timestamp must include timezone"
                                        )
                                    else:
                                        parsed_utc = parsed_timestamp.astimezone(
                                            timezone.utc
                                        )
                                        if (
                                            previous_timestamp is not None
                                            and parsed_utc < previous_timestamp
                                        ):
                                            findings.append(
                                                f"audit {sequence}: timestamp precedes an earlier audit event"
                                            )
                                        if (
                                            previous_timestamp is None
                                            or parsed_utc > previous_timestamp
                                        ):
                                            previous_timestamp = parsed_utc
                                except (TypeError, ValueError, OverflowError):
                                    findings.append(
                                        f"audit {sequence}: invalid recorded_at timestamp"
                                    )
                            key = audit["idempotency_key"]
                            event_identity = (
                                str(key),
                                audit["dispatch_generation"],
                                str(audit["decision"]),
                                str(audit["evidence"]),
                            )
                            if event_identity in seen_audit_events:
                                findings.append(
                                    f"audit {sequence}: duplicate reconciliation event"
                                )
                            else:
                                seen_audit_events.add(event_identity)
                            record = records_by_key.get(key)
                            if record is None:
                                findings.append(
                                    f"audit {sequence}: orphan idempotency key {key!r}"
                                )
                                continue
                            if (
                                not isinstance(audit["evidence"], str)
                                or not audit["evidence"].strip()
                            ):
                                findings.append(f"audit {sequence}: empty evidence")
                            if audit["decision"] not in ("completed", "not_executed"):
                                findings.append(
                                    f"audit {sequence}: invalid decision {audit['decision']!r}"
                                )
                            generation = audit["dispatch_generation"]
                            if (
                                not isinstance(generation, int)
                                or generation < 0
                                or generation > record.dispatch_generation
                            ):
                                findings.append(
                                    f"audit {sequence}: invalid dispatch generation"
                                )
                            elif isinstance(key, str):
                                prior_generation = last_generation_by_key.get(key)
                                if (
                                    prior_generation is not None
                                    and generation < prior_generation
                                ):
                                    findings.append(
                                        f"audit {sequence}: dispatch generation regresses for idempotency key {key!r}"
                                    )
                                elif (
                                    prior_generation is not None
                                    and generation > prior_generation + 1
                                ):
                                    findings.append(
                                        f"audit {sequence}: dispatch generation gap for idempotency key {key!r}; "
                                        f"expected at most {prior_generation + 1}, found {generation}"
                                    )
                                if (
                                    prior_generation is None
                                    or generation > prior_generation
                                ):
                                    last_generation_by_key[key] = generation
                                if (
                                    key not in latest_audit_generation_by_key
                                    or generation > latest_audit_generation_by_key[key]
                                ):
                                    latest_audit_generation_by_key[key] = generation
                                if audit["decision"] in ("completed", "not_executed"):
                                    decision_key = (key, generation)
                                    prior_decision = decision_by_key_generation.get(
                                        decision_key
                                    )
                                    if (
                                        prior_decision is not None
                                        and prior_decision != audit["decision"]
                                    ):
                                        findings.append(
                                            f"audit {sequence}: conflicting reconciliation decisions for "
                                            f"idempotency key {key!r} generation {generation}"
                                        )
                                    else:
                                        decision_by_key_generation[decision_key] = (
                                            audit["decision"]
                                        )
                                if audit["decision"] == "not_executed" and isinstance(
                                    audit["evidence"], str
                                ):
                                    evidence_key = (key, audit["evidence"])
                                    prior_evidence_generation = (
                                        not_executed_evidence_generation.get(
                                            evidence_key
                                        )
                                    )
                                    if (
                                        prior_evidence_generation is not None
                                        and generation > prior_evidence_generation
                                    ):
                                        findings.append(
                                            f"audit {sequence}: not_executed evidence was reused after a later dispatch generation"
                                        )
                                    if (
                                        prior_evidence_generation is None
                                        or generation > prior_evidence_generation
                                    ):
                                        not_executed_evidence_generation[
                                            evidence_key
                                        ] = generation
                            if (
                                audit["decision"] == "completed"
                                and record.status is not IdempotencyStatus.COMPLETED
                            ):
                                findings.append(
                                    f"audit {sequence}: completed decision has non-completed record"
                                )
                            if (
                                audit["decision"] == "not_executed"
                                and record.status is IdempotencyStatus.COMPLETED
                            ):
                                findings.append(
                                    f"audit {sequence}: not_executed decision conflicts with completed record"
                                )
                        # A record with dispatch history must not silently outpace its
                        # reconciliation history. Otherwise a backup could validate even
                        # though the most recent dispatch generation has no audit evidence.
                        for key, record in records_by_key.items():
                            audited_generation = latest_audit_generation_by_key.get(key)
                            if (
                                record.dispatch_generation > 0
                                and audited_generation is None
                            ):
                                findings.append(
                                    f"audit: missing reconciliation history for dispatched idempotency key {key!r}"
                                )
                            elif (
                                audited_generation is not None
                                and audited_generation != record.dispatch_generation
                            ):
                                findings.append(
                                    f"audit: latest dispatch generation mismatch for idempotency key {key!r}; "
                                    f"record has {record.dispatch_generation}, audit has {audited_generation}"
                                )
                    except sqlite3.DatabaseError as exc:
                        findings.append(
                            f"audit: cannot read reconciliation records: {exc}"
                        )
            return tuple(findings)
        except sqlite3.DatabaseError as exc:
            return tuple(findings + [f"backup: cannot validate SQLite database: {exc}"])
        finally:
            connection.close()

    def backup_to(self, destination_path: str | Path) -> str:
        """Create and validate a consistent backup, then publish without overwriting.

        A temporary database is built beside the target, validated read-only, and
        published with a same-filesystem hard link. The final link operation fails
        if another process has already created the destination, avoiding silent
        replacement of an existing backup.
        """
        if (
            not isinstance(destination_path, (str, Path))
            or not str(destination_path).strip()
        ):
            raise ValueError("destination_path must not be empty")
        destination_path_obj = Path(destination_path).expanduser()
        destination_text = str(destination_path_obj)
        if destination_text == ":memory:":
            raise ValueError("backup destination must be a file-backed database")
        destination_resolved = destination_path_obj.resolve()
        if self._database_path != ":memory:":
            source_resolved = Path(self._database_path).expanduser().resolve()
            if source_resolved == destination_resolved:
                raise ValueError("backup destination must differ from source database")
        if not destination_resolved.parent.is_dir():
            raise ValueError("backup destination parent directory must exist")
        if destination_resolved.exists():
            raise FileExistsError(
                f"backup destination already exists: {destination_resolved}"
            )
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{destination_resolved.name}.",
            suffix=".tmp",
            dir=destination_resolved.parent,
        )
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with self._lock:
                destination = sqlite3.connect(str(temporary), timeout=30)
                try:
                    self._connection.backup(destination)
                    destination.commit()
                finally:
                    destination.close()
            findings = self.validate_backup(temporary)
            if findings:
                raise sqlite3.DatabaseError(
                    "backup validation failed: " + "; ".join(findings)
                )
            # link() is atomic and will not overwrite a destination created by a race.
            os.link(temporary, destination_resolved)
            return str(destination_resolved)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def close(self) -> None:
        with self._lock:
            self._connection.close()
