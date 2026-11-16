from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True, slots=True)
class StoredInvestigationRecord:
    """Latest durable revision of a JSON-compatible investigation record."""
    record_type: str
    record_id: str
    revision: int
    payload: dict[str, Any]
    checksum: str
    created_at_iso: str


@dataclass(frozen=True, slots=True)
class InvestigationRecordVersion:
    """One immutable revision in a per-record checksum chain."""
    record_type: str
    record_id: str
    revision: int
    payload: dict[str, Any]
    checksum: str
    previous_checksum: str | None
    created_at_iso: str


@dataclass(frozen=True, slots=True)
class InvestigationStoreIntegrityIssue:
    """A stable, machine-readable integrity finding; verification never repairs data."""
    record_type: str
    record_id: str
    revision: int | None
    code: str
    message: str


class InvestigationStoreIntegrityError(RuntimeError):
    """Raised when a requested record has a corrupt or discontinuous revision chain."""


class InvestigationRevisionConflict(RuntimeError):
    """Raised when optimistic concurrency expected a different current revision."""


class DiagnosticInvestigationStore:
    """SQLite-backed versioned store for JSON investigation snapshots and artifacts.

    Callers serialize domain snapshots into JSON-compatible mappings. Saves are atomic
    and append-only, guarded by an expected revision (0 means create-only). Domain
    objects are not persisted automatically; integration code must explicitly save and
    restore snapshots. Integrity hashes detect data edits that do not also recompute the chain; they are not
    keyed signatures and do not replace access control, backups, or external audit protection.
    """
    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path) -> None:
        if not isinstance(path, (str, Path)):
            raise TypeError("path must be a filesystem path or ':memory:'")
        raw_path = str(path)
        if not raw_path.strip():
            raise ValueError("path must be non-empty")
        if raw_path != ":memory:":
            Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._closed = False
        self._connection = sqlite3.connect(raw_path, timeout=5.0, isolation_level=None, check_same_thread=False)
        try:
            self._connection.row_factory = sqlite3.Row
            with self._lock:
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute("PRAGMA busy_timeout = 5000")
                self._connection.execute("PRAGMA synchronous = FULL")
                if raw_path != ":memory:":
                    self._connection.execute("PRAGMA journal_mode = WAL")
                self._connection.execute("""
                    CREATE TABLE IF NOT EXISTS investigation_record_versions (
                        record_type TEXT NOT NULL,
                        record_id TEXT NOT NULL,
                        revision INTEGER NOT NULL CHECK (revision > 0),
                        payload_json TEXT NOT NULL,
                        checksum TEXT NOT NULL,
                        previous_checksum TEXT,
                        created_at_iso TEXT NOT NULL,
                        PRIMARY KEY (record_type, record_id, revision)
                    )
                """)
                self._connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        except BaseException:
            self._connection.close()
            self._closed = True
            raise

    @staticmethod
    def _validate_identity(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _canonical_payload(payload: Any) -> str:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a JSON-compatible mapping/dict")
        try:
            return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"payload must contain only finite JSON-compatible values: {exc}") from exc

    @staticmethod
    def _checksum(record_type: str, record_id: str, revision: int, payload_json: str,
                  previous_checksum: str | None) -> str:
        body = json.dumps([record_type, record_id, revision, payload_json, previous_checksum],
                          separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(body).hexdigest()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("investigation store is closed")

    @staticmethod
    def _decode(row: sqlite3.Row) -> InvestigationRecordVersion:
        try:
            payload = json.loads(row["payload_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise InvestigationStoreIntegrityError(
                f"invalid JSON payload for {row['record_type']}/{row['record_id']} revision {row['revision']}"
            ) from exc
        if not isinstance(payload, dict):
            raise InvestigationStoreIntegrityError(
                f"payload is not an object for {row['record_type']}/{row['record_id']} revision {row['revision']}"
            )
        return InvestigationRecordVersion(
            row["record_type"], row["record_id"], row["revision"], payload, row["checksum"],
            row["previous_checksum"], row["created_at_iso"],
        )

    def _rows_for_key(self, record_type: str, record_id: str) -> list[sqlite3.Row]:
        return list(self._connection.execute(
            "SELECT * FROM investigation_record_versions WHERE record_type=? AND record_id=? ORDER BY revision",
            (record_type, record_id),
        ))

    @staticmethod
    def _parse_timestamp(value: object) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed

    def _check_chain(self, record_type: str, record_id: str,
                     rows: list[sqlite3.Row]) -> tuple[InvestigationRecordVersion, ...]:
        previous: str | None = None
        previous_timestamp: datetime | None = None
        decoded: list[InvestigationRecordVersion] = []
        for expected_revision, row in enumerate(rows, start=1):
            revision = row["revision"]
            if revision != expected_revision:
                raise InvestigationStoreIntegrityError(
                    f"revision gap for {record_type}/{record_id}: expected {expected_revision}, found {revision}"
                )
            if row["previous_checksum"] != previous:
                raise InvestigationStoreIntegrityError(
                    f"previous checksum mismatch for {record_type}/{record_id} revision {revision}"
                )
            expected = self._checksum(record_type, record_id, revision, row["payload_json"], previous)
            if row["checksum"] != expected:
                raise InvestigationStoreIntegrityError(
                    f"checksum mismatch for {record_type}/{record_id} revision {revision}"
                )
            timestamp = self._parse_timestamp(row["created_at_iso"])
            if timestamp is None:
                raise InvestigationStoreIntegrityError(
                    f"created_at timestamp invalid for {record_type}/{record_id} revision {revision}"
                )
            if previous_timestamp is not None and timestamp < previous_timestamp:
                raise InvestigationStoreIntegrityError(
                    f"created_at timestamp reversed for {record_type}/{record_id} revision {revision}"
                )
            decoded.append(self._decode(row))
            previous = row["checksum"]
            previous_timestamp = timestamp
        return tuple(decoded)

    def save(self, record_type: str, record_id: str, payload: dict[str, Any], *,
             expected_revision: int = 0) -> StoredInvestigationRecord:
        """Create/update atomically; expected_revision=0 creates, N updates revision N."""
        record_type = self._validate_identity(record_type, "record_type")
        record_id = self._validate_identity(record_id, "record_id")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ValueError("expected_revision must be a non-negative integer")
        payload_json = self._canonical_payload(payload)
        with self._lock:
            self._ensure_open()
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                chain = self._check_chain(record_type, record_id, self._rows_for_key(record_type, record_id))
                current_revision = chain[-1].revision if chain else 0
                if current_revision != expected_revision:
                    raise InvestigationRevisionConflict(
                        f"expected revision {expected_revision}, current revision is {current_revision}"
                    )
                revision = current_revision + 1
                previous_checksum = chain[-1].checksum if chain else None
                checksum = self._checksum(record_type, record_id, revision, payload_json, previous_checksum)
                created_at = datetime.now(timezone.utc).isoformat()
                self._connection.execute(
                    "INSERT INTO investigation_record_versions "
                    "(record_type, record_id, revision, payload_json, checksum, previous_checksum, created_at_iso) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (record_type, record_id, revision, payload_json, checksum, previous_checksum, created_at),
                )
                self._connection.execute("COMMIT")
            except Exception:
                self._connection.execute("ROLLBACK")
                raise
        return StoredInvestigationRecord(record_type, record_id, revision, json.loads(payload_json), checksum, created_at)

    def load(self, record_type: str, record_id: str) -> StoredInvestigationRecord | None:
        record_type = self._validate_identity(record_type, "record_type")
        record_id = self._validate_identity(record_id, "record_id")
        with self._lock:
            self._ensure_open()
            chain = self._check_chain(record_type, record_id, self._rows_for_key(record_type, record_id))
        if not chain:
            return None
        latest = chain[-1]
        return StoredInvestigationRecord(latest.record_type, latest.record_id, latest.revision,
                                         latest.payload, latest.checksum, latest.created_at_iso)

    def history(self, record_type: str, record_id: str) -> tuple[InvestigationRecordVersion, ...]:
        record_type = self._validate_identity(record_type, "record_type")
        record_id = self._validate_identity(record_id, "record_id")
        with self._lock:
            self._ensure_open()
            return self._check_chain(record_type, record_id, self._rows_for_key(record_type, record_id))

    def verify_integrity(self) -> tuple[InvestigationStoreIntegrityIssue, ...]:
        """Read-only integrity scan over all retained revision chains and metadata."""
        with self._lock:
            self._ensure_open()
            keys = self._connection.execute(
                "SELECT DISTINCT record_type, record_id FROM investigation_record_versions ORDER BY record_type, record_id"
            ).fetchall()
            issues: list[InvestigationStoreIntegrityIssue] = []
            for key in keys:
                record_type, record_id = key["record_type"], key["record_id"]
                rows = self._rows_for_key(record_type, record_id)
                try:
                    self._check_chain(record_type, record_id, rows)
                except InvestigationStoreIntegrityError as exc:
                    message = str(exc)
                    revision = None
                    if " revision " in message:
                        try:
                            revision = int(message.rsplit(" revision ", 1)[1])
                        except ValueError:
                            pass
                    code = "revision_chain_invalid"
                    if "checksum mismatch" in message:
                        code = "checksum_mismatch"
                    elif "previous checksum mismatch" in message:
                        code = "previous_checksum_mismatch"
                    elif "invalid JSON" in message or "not an object" in message:
                        code = "invalid_payload"
                    elif "revision gap" in message:
                        code = "revision_gap"
                    elif "created_at timestamp invalid" in message:
                        code = "created_at_invalid"
                    elif "created_at timestamp reversed" in message:
                        code = "created_at_time_reversed"
                    issues.append(InvestigationStoreIntegrityIssue(record_type, record_id, revision, code, message))

                # Audit timestamps independently: an invalid checksum must not hide a
                # separate metadata defect. This scan is read-only and deterministic.
                previous_timestamp: datetime | None = None
                for row in rows:
                    timestamp = self._parse_timestamp(row["created_at_iso"])
                    revision = row["revision"]
                    if timestamp is None:
                        issues.append(InvestigationStoreIntegrityIssue(
                            record_type, record_id, revision, "created_at_invalid",
                            f"created_at timestamp must be ISO-8601 with an explicit timezone for {record_type}/{record_id} revision {revision}",
                        ))
                    elif previous_timestamp is not None and timestamp < previous_timestamp:
                        issues.append(InvestigationStoreIntegrityIssue(
                            record_type, record_id, revision, "created_at_time_reversed",
                            f"created_at timestamp moves backwards for {record_type}/{record_id} revision {revision}",
                        ))
                    if timestamp is not None:
                        previous_timestamp = timestamp
            # Chain validation and the independent metadata scan intentionally overlap:
            # the former rejects unsafe reads while the latter can report additional
            # timestamp defects after an earlier checksum/JSON failure. Keep that
            # overlap from emitting the *same* finding twice, without suppressing
            # distinct defects on the same revision.
            unique_issues = {}
            for item in issues:
                # The chain check and metadata-only check use different wording for
                # the same timestamp defect, so identify those by their stable code.
                message_key = None if item.code in {"created_at_invalid", "created_at_time_reversed"} else item.message
                key = (item.record_type, item.record_id, item.revision, item.code, message_key)
                unique_issues.setdefault(key, item)
            issues = list(unique_issues.values())
            issues.sort(key=lambda item: (
                item.record_type, item.record_id, item.revision or 0, item.code, item.message
            ))
            return tuple(issues)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def __enter__(self) -> DiagnosticInvestigationStore:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
