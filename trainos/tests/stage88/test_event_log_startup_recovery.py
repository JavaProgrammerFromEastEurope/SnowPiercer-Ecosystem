from tests.sqlite_resource_helpers import managed_sqlite_connection
from datetime import datetime, timezone
import sqlite3

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogStartupRecovery, StartupRecoveryStatus,
)


def _event(event_id: str, value: int = 1) -> CommandEvent:
    return CommandEvent(
        event_id=event_id, command_id="startup-test",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"value": value},
    )


def _trusted(tmp_path):
    store = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    store.append(_event("e1"))
    anchors.create_anchor(store)
    return store, anchors


def test_startup_accepts_verified_active_log(tmp_path):
    store, anchors = _trusted(tmp_path)
    result = EventLogStartupRecovery.run(store.database_path, anchors)
    assert result.status is StartupRecoveryStatus.TRUSTED
    assert result.recovery_path is None
    store.close()
    anchors.close()


def test_startup_requires_recovery_when_active_log_is_missing(tmp_path):
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    result = EventLogStartupRecovery.run(tmp_path / "missing.sqlite", anchors)
    assert result.status is StartupRecoveryStatus.RECOVERY_REQUIRED
    assert result.findings[0]["code"] == "active_log_missing"
    anchors.close()


def test_startup_prepares_verified_candidate_without_replacing_active_log(tmp_path):
    store, anchors = _trusted(tmp_path)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(store, anchors, backup)
    with managed_sqlite_connection(store.database_path) as connection:
        connection.execute("UPDATE command_events SET payload_json = ? WHERE event_id = ?",
                           ('{"value":999}', "e1"))
    result = EventLogStartupRecovery.run(
        store.database_path, anchors, backup_path=backup,
        recovery_destination_path=tmp_path / "recovery-candidate.sqlite",
    )
    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    assert result.recovery_path == str((tmp_path / "recovery-candidate.sqlite").resolve())
    assert EventLogStartupRecovery.run(store.database_path, anchors).status is StartupRecoveryStatus.RECOVERY_REQUIRED
    store.close()
    anchors.close()


def test_startup_rejects_stale_backup_and_does_not_publish_candidate(tmp_path):
    store, anchors = _trusted(tmp_path)
    stale_store = CommandEventStore(tmp_path / "stale-source.sqlite")
    stale_anchors = EventIntegrityAnchorStore(tmp_path / "stale-anchors.sqlite")
    stale_store.append(_event("e1"))
    stale_anchors.create_anchor(stale_store)
    stale_backup = tmp_path / "stale-backup.sqlite"
    EventLogBackupManager.create_backup(stale_store, stale_anchors, stale_backup)
    store.append(_event("e2", 2))
    anchors.create_anchor(store)
    with managed_sqlite_connection(store.database_path) as connection:
        connection.execute("UPDATE command_events SET payload_json = ? WHERE event_id = ?",
                           ('{"value":999}', "e1"))
    destination = tmp_path / "rejected-candidate.sqlite"

    result = EventLogStartupRecovery.run(
        store.database_path, anchors, backup_path=stale_backup,
        recovery_destination_path=destination,
    )
    assert result.status is StartupRecoveryStatus.BLOCKED
    assert not destination.exists()
    assert result.findings[-1]["code"] == "recovery_candidate_rejected"
    store.close()
    anchors.close()
    stale_store.close()
    stale_anchors.close()


def test_startup_does_not_overwrite_existing_recovery_candidate(tmp_path):
    store, anchors = _trusted(tmp_path)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(store, anchors, backup)
    with managed_sqlite_connection(store.database_path) as connection:
        connection.execute("UPDATE command_events SET payload_json = ? WHERE event_id = ?",
                           ('{"value":999}', "e1"))
    destination = tmp_path / "candidate.sqlite"
    destination.write_bytes(b"preserve-existing")
    result = EventLogStartupRecovery.run(
        store.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination,
    )
    assert result.status is StartupRecoveryStatus.BLOCKED
    assert destination.read_bytes() == b"preserve-existing"
    store.close()
    anchors.close()


def test_startup_never_restores_directly_into_active_database_path(tmp_path):
    store, anchors = _trusted(tmp_path)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(store, anchors, backup)
    active_path = store.database_path
    store.close()
    # Simulate an absent active DB; startup must not use the active path as candidate.
    import os
    os.unlink(active_path)
    result = EventLogStartupRecovery.run(
        active_path, anchors, backup_path=backup,
        recovery_destination_path=active_path,
    )
    assert result.status is StartupRecoveryStatus.BLOCKED
    assert not __import__("pathlib").Path(active_path).exists()
    assert result.findings[-1]["code"] == "recovery_path_collision"
    anchors.close()
