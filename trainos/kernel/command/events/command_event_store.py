from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Iterator

from .command_event import CommandEvent
from .event_type import CommandEventType


class CommandEventStore:
    """Append-only SQLite persistence for command events.

    This is durable application storage, not a tamper-proof or safety-certified log.
    Duplicate event IDs are idempotent only when the stored envelope is identical.
    """

    def __init__(self, database_path: str | Path) -> None:
        if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
            raise ValueError("database_path must not be empty")
        self._database_path = str(database_path)
        self._lock = RLock()
        self._anchor_store = None
        self._require_trusted_reads = False
        self._connection = sqlite3.connect(self._database_path, check_same_thread=False)
        try:
            self._connection.row_factory = sqlite3.Row
            with self._lock, self._connection:
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute("""CREATE TABLE IF NOT EXISTS command_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    command_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT,
                    event_hash TEXT
                )""")
                columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(command_events)")}
                if "previous_hash" not in columns:
                    self._connection.execute("ALTER TABLE command_events ADD COLUMN previous_hash TEXT")
                if "event_hash" not in columns:
                    self._connection.execute("ALTER TABLE command_events ADD COLUMN event_hash TEXT")
                # Existing rows are anchored during migration; this cannot prove their pre-migration authenticity.
                legacy_rows = self._connection.execute(
                    "SELECT sequence, event_id, command_id, event_type, timestamp, payload_json, event_hash "
                    "FROM command_events ORDER BY sequence"
                ).fetchall()
                if any(row["event_hash"] is None for row in legacy_rows):
                    # Re-anchor the entire pre-feature history during migration. This cannot prove
                    # the authenticity of rows that existed before hashes were introduced.
                    previous_hash = "0" * 64
                    for row in legacy_rows:
                        envelope = (row["event_id"], row["command_id"], row["event_type"], row["timestamp"], row["payload_json"])
                        digest = self._calculate_hash(previous_hash, envelope)
                        self._connection.execute(
                            "UPDATE command_events SET previous_hash = ?, event_hash = ? WHERE sequence = ?",
                            (previous_hash, digest, row["sequence"]),
                        )
                        previous_hash = digest
                self._connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_command_events_command ON command_events(command_id, sequence)"
                )

        except BaseException:
            self._connection.close()
            raise

    @property
    def database_path(self) -> str:
        return self._database_path

    @staticmethod
    def _calculate_hash(previous_hash: str, envelope: tuple[str, str, str, str, str]) -> str:
        encoded = json.dumps(
            {"previous_hash": previous_hash, "event": envelope},
            separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _serialize(event: CommandEvent) -> tuple[str, str, str, str, str]:
        if not isinstance(event, CommandEvent):
            raise TypeError("event must be a CommandEvent")
        payload = json.dumps(event.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return (event.event_id, event.command_id, event.event_type.value,
                event.timestamp.isoformat(), payload)

    @staticmethod
    def _deserialize(row: sqlite3.Row) -> CommandEvent:
        return CommandEvent(
            event_id=row["event_id"], command_id=row["command_id"],
            event_type=CommandEventType(row["event_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            payload=json.loads(row["payload_json"]),
        )

    def append(self, event: CommandEvent) -> None:
        values = self._serialize(event)
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT event_id, command_id, event_type, timestamp, payload_json "
                "FROM command_events WHERE event_id = ?", (event.event_id,),
            ).fetchone()
            if row is not None:
                if tuple(row) != values:
                    raise ValueError("conflicting duplicate event_id")
                return
            previous = self._connection.execute(
                "SELECT event_hash FROM command_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else "0" * 64
            event_hash = self._calculate_hash(previous_hash, values)
            self._connection.execute(
                "INSERT INTO command_events(event_id, command_id, event_type, timestamp, payload_json, previous_hash, event_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)", (*values, previous_hash, event_hash),
            )

    def enable_trusted_reads(self, anchor_store: object) -> None:
        """Require a fresh recovery-gate assessment before public event reads.

        This is an application-level guard; integrity metadata methods remain available
        to the verifier and are not substitutes for an independently protected anchor.
        """
        from .event_integrity_anchor_store import EventIntegrityAnchorStore
        if not isinstance(anchor_store, EventIntegrityAnchorStore):
            raise TypeError("anchor_store must be an EventIntegrityAnchorStore")
        if getattr(anchor_store, "database_path", None) == self._database_path:
            raise ValueError("event and anchor stores must use separate database paths")
        with self._lock:
            self._anchor_store = anchor_store
            self._require_trusted_reads = True

    def _require_trusted_history(self) -> None:
        if self._require_trusted_reads:
            from .event_log_recovery_gate import EventLogRecoveryGate
            EventLogRecoveryGate.require_verified(self, self._anchor_store)

    @contextmanager
    def _read_snapshot(self) -> Iterator[None]:
        """Keep trust assessment and the corresponding read in one SQLite snapshot.

        The store lock excludes mutations through this instance. A SQLite read
        transaction additionally prevents an external connection from making the
        event rows change between verification and retrieval. If a caller already
        owns a transaction, its transaction boundary remains the caller's concern.
        """
        with self._lock:
            owns_transaction = self._require_trusted_reads and not self._connection.in_transaction
            if owns_transaction:
                self._connection.execute("BEGIN")
            try:
                self._require_trusted_history()
                yield
                if owns_transaction:
                    self._connection.commit()
            except BaseException:
                if owns_transaction and self._connection.in_transaction:
                    self._connection.rollback()
                raise

    def get_events(self, command_id: str) -> tuple[CommandEvent, ...]:
        if not isinstance(command_id, str) or not command_id.strip():
            raise ValueError("command_id must not be empty")
        with self._read_snapshot():
            rows = self._connection.execute(
                "SELECT event_id, command_id, event_type, timestamp, payload_json "
                "FROM command_events WHERE command_id = ? ORDER BY sequence", (command_id,),
            ).fetchall()
        return tuple(self._deserialize(row) for row in rows)

    def all_events(self) -> tuple[CommandEvent, ...]:
        with self._read_snapshot():
            rows = self._connection.execute(
                "SELECT event_id, command_id, event_type, timestamp, payload_json "
                "FROM command_events"
            ).fetchall()
        events = [self._deserialize(row) for row in rows]
        return tuple(sorted(events, key=lambda event: (event.timestamp, event.event_id)))


    def verify_integrity(self) -> tuple[dict[str, object], ...]:
        """Read-only audit of the event hash chain; not protection against full DB rewrite."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT sequence, event_id, command_id, event_type, timestamp, payload_json, previous_hash, event_hash "
                "FROM command_events ORDER BY sequence"
            ).fetchall()
        findings: list[dict[str, object]] = []
        previous_hash = "0" * 64
        expected_sequence = rows[0]["sequence"] if rows else 1
        for row in rows:
            sequence = row["sequence"]
            if sequence != expected_sequence:
                findings.append({"code": "sequence_gap", "sequence": sequence,
                                 "expected_sequence": expected_sequence})
            expected_sequence = sequence + 1
            envelope = (row["event_id"], row["command_id"], row["event_type"],
                        row["timestamp"], row["payload_json"])
            if row["previous_hash"] != previous_hash:
                findings.append({"code": "previous_hash_mismatch", "sequence": sequence,
                                 "event_id": row["event_id"]})
            expected_hash = self._calculate_hash(previous_hash, envelope)
            if row["event_hash"] != expected_hash:
                findings.append({"code": "event_hash_mismatch", "sequence": sequence,
                                 "event_id": row["event_id"]})
            previous_hash = row["event_hash"] or ""
        return tuple(findings)

    def integrity_snapshot(self) -> tuple[tuple[dict[str, object], ...], tuple[int, str], dict[int, str | None]]:
        """Return findings and chain references from one SQLite read snapshot.

        The findings, current head, and per-sequence hashes must describe the same
        database state; callers use this when creating or checking external anchors.
        """
        with self._lock:
            owns_transaction = not self._connection.in_transaction
            if owns_transaction:
                self._connection.execute("BEGIN")
            try:
                findings = self.verify_integrity()
                head = self.integrity_head()
                rows = self._connection.execute(
                    "SELECT sequence, event_hash FROM command_events ORDER BY sequence"
                ).fetchall()
                hashes = {int(row["sequence"]): row["event_hash"] for row in rows}
                if owns_transaction:
                    self._connection.commit()
            except BaseException:
                if owns_transaction and self._connection.in_transaction:
                    self._connection.rollback()
                raise
        return findings, head, hashes

    def integrity_head(self) -> tuple[int, str]:
        """Return the current append sequence and hash (genesis for an empty log)."""
        with self._lock:
            row = self._connection.execute(
                "SELECT sequence, event_hash FROM command_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return (0, "0" * 64)
        return (int(row["sequence"]), str(row["event_hash"] or ""))

    def integrity_hash_at(self, sequence: int) -> str | None:
        """Return a stored chain hash for an exact sequence, or None if absent."""
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("sequence must be a positive integer")
        with self._lock:
            row = self._connection.execute(
                "SELECT event_hash FROM command_events WHERE sequence = ?", (sequence,)
            ).fetchone()
        return None if row is None else row["event_hash"]

    def close(self) -> None:
        with self._lock:
            self._connection.close()
