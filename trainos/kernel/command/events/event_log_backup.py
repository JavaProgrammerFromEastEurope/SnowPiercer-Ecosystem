"""Verified SQLite backups and fail-closed event-log restoration.

Backups are copied with SQLite's online backup API, not filesystem copying, so
committed pages are captured consistently even when the source database uses WAL.
This module is an application-level recovery aid, not an immutable backup system.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path

from .command_event_store import CommandEventStore
from .event_integrity_anchor_store import EventIntegrityAnchorStore
from .event_log_recovery_gate import EventLogRecoveryAssessment, EventLogRecoveryGate


class EventLogBackupManager:
    """Create and restore event-log backups only when an independent anchor verifies them."""

    @staticmethod
    def _path(value: str | Path, name: str) -> Path:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise ValueError(f"{name} must not be empty")
        return Path(value).expanduser().resolve()

    @staticmethod
    def fingerprint_file(path: str | Path) -> str:
        """Return a SHA-256 fingerprint for a closed, standalone backup file."""
        source = EventLogBackupManager._path(path, "path")
        if not source.is_file():
            raise FileNotFoundError(source)
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _fsync_file(path: Path) -> None:
        """Flush file contents before making the file visible as a recovery artifact."""
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        """Flush directory-entry changes on platforms that support directory fsync."""
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _publish_no_clobber(temporary_path: Path, target_path: Path) -> None:
        """Durably publish a complete file without replacing a racing destination.

        Both paths must be on the same filesystem. The file is flushed before the
        atomic hard-link publication; the parent directory is flushed after linking
        and after removing the temporary name. If a durability operation fails after
        linking, the method raises but deliberately leaves the published target in
        place for the startup reconciliation path to verify. It never falls back to
        a replace operation that could overwrite a competing file.
        """
        EventLogBackupManager._fsync_file(temporary_path)
        os.link(temporary_path, target_path)
        EventLogBackupManager._fsync_directory(target_path.parent)
        temporary_path.unlink()
        EventLogBackupManager._fsync_directory(target_path.parent)

    @staticmethod
    def _copy_sqlite(source: Path, destination: Path) -> None:
        if not source.is_file():
            raise FileNotFoundError(source)
        source_uri = f"file:{source.as_posix()}?mode=ro"
        source_connection = sqlite3.connect(source_uri, uri=True, timeout=5.0)
        try:
            destination_connection = sqlite3.connect(str(destination), timeout=5.0)
            try:
                source_connection.backup(destination_connection)
                destination_connection.commit()
            finally:
                destination_connection.close()
        finally:
            source_connection.close()

    @staticmethod
    def _assess_database(database_path: Path,
                        anchor_store: EventIntegrityAnchorStore) -> EventLogRecoveryAssessment:
        store = CommandEventStore(database_path)
        try:
            return EventLogRecoveryGate.assess(store, anchor_store)
        finally:
            store.close()

    @classmethod
    def create_backup(
        cls,
        event_store: CommandEventStore,
        anchor_store: EventIntegrityAnchorStore,
        backup_path: str | Path,
    ) -> EventLogRecoveryAssessment:
        """Create a new backup, publish it only after independent-anchor validation.

        Existing destinations are rejected rather than silently overwritten. A failed
        capture or verification removes the temporary file and leaves no published backup.
        """
        if not isinstance(event_store, CommandEventStore):
            raise TypeError("event_store must be a CommandEventStore")
        if not isinstance(anchor_store, EventIntegrityAnchorStore):
            raise TypeError("anchor_store must be an EventIntegrityAnchorStore")
        target = cls._path(backup_path, "backup_path")
        if target in {Path(event_store.database_path).expanduser().resolve(),
                      Path(anchor_store.database_path).expanduser().resolve()}:
            raise ValueError("backup path must be separate from event and anchor databases")
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        os.close(fd)
        temp = Path(temp_name)
        try:
            with event_store._lock:
                destination = sqlite3.connect(str(temp), timeout=5.0)
                try:
                    event_store._connection.backup(destination)
                    destination.commit()
                finally:
                    destination.close()
            assessment = cls._assess_database(temp, anchor_store)
            if not assessment.trusted_for_read:
                raise RuntimeError(
                    f"backup verification failed: status={assessment.status.value}; "
                    f"findings={assessment.findings!r}"
                )
            # Atomic no-clobber publication closes the exists-check/replace race.
            cls._publish_no_clobber(temp, target)
            return assessment
        finally:
            temp.unlink(missing_ok=True)

    @classmethod
    def verify_backup(
        cls,
        backup_path: str | Path,
        anchor_store: EventIntegrityAnchorStore,
    ) -> EventLogRecoveryAssessment:
        """Assess a backup through a temporary SQLite snapshot without modifying its source."""
        if not isinstance(anchor_store, EventIntegrityAnchorStore):
            raise TypeError("anchor_store must be an EventIntegrityAnchorStore")
        source = cls._path(backup_path, "backup_path")
        if source.resolve() == Path(anchor_store.database_path).expanduser().resolve():
            raise ValueError("backup path must be separate from anchor database")
        if not source.is_file():
            raise FileNotFoundError(source)
        fd, temp_name = tempfile.mkstemp(prefix="trainos-verify-", suffix=".sqlite")
        os.close(fd)
        temp = Path(temp_name)
        try:
            cls._copy_sqlite(source, temp)
            return cls._assess_database(temp, anchor_store)
        finally:
            temp.unlink(missing_ok=True)

    @classmethod
    def restore_backup(
        cls,
        backup_path: str | Path,
        destination_path: str | Path,
        anchor_store: EventIntegrityAnchorStore,
        *,
        expected_sha256: str | None = None,
    ) -> EventLogRecoveryAssessment:
        """Restore to a new path, publishing it only after verification succeeds."""
        if not isinstance(anchor_store, EventIntegrityAnchorStore):
            raise TypeError("anchor_store must be an EventIntegrityAnchorStore")
        source = cls._path(backup_path, "backup_path")
        target = cls._path(destination_path, "destination_path")
        anchor_path = Path(anchor_store.database_path).expanduser().resolve()
        if source == target or target == anchor_path or source == anchor_path:
            raise ValueError("backup, destination, and anchor databases must use separate paths")
        if not source.is_file():
            raise FileNotFoundError(source)
        source_fingerprint = cls.fingerprint_file(source)
        if expected_sha256 is not None and source_fingerprint != expected_sha256:
            raise RuntimeError("backup fingerprint does not match the authorized checkpoint")
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".restore", dir=target.parent)
        os.close(fd)
        temp = Path(temp_name)
        try:
            cls._copy_sqlite(source, temp)
            if cls.fingerprint_file(source) != source_fingerprint:
                raise RuntimeError("backup changed while recovery candidate was being copied")
            assessment = cls._assess_database(temp, anchor_store)
            if not assessment.trusted_for_read:
                raise RuntimeError(
                    f"restore verification failed: status={assessment.status.value}; "
                    f"findings={assessment.findings!r}"
                )
            cls._publish_no_clobber(temp, target)
            return assessment
        finally:
            temp.unlink(missing_ok=True)
