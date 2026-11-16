from datetime import datetime, timezone
import sqlite3

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogTrustStatus,
)


def _event(event_id: str, value: int = 1) -> CommandEvent:
    return CommandEvent(
        event_id=event_id,
        command_id="backup-test",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        payload={"value": value},
    )


def _stores(tmp_path):
    events = CommandEventStore(tmp_path / "events.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    events.append(_event("e1"))
    anchors.create_anchor(events)
    return events, anchors


def test_create_backup_and_restore_verified_snapshot(tmp_path):
    events, anchors = _stores(tmp_path)
    backup = tmp_path / "backup.sqlite"
    restored_path = tmp_path / "restored.sqlite"

    created = EventLogBackupManager.create_backup(events, anchors, backup)
    verified = EventLogBackupManager.verify_backup(backup, anchors)
    restored = EventLogBackupManager.restore_backup(backup, restored_path, anchors)

    assert created.status is EventLogTrustStatus.VERIFIED
    assert verified.status is EventLogTrustStatus.VERIFIED
    assert restored.status is EventLogTrustStatus.VERIFIED
    restored_store = CommandEventStore(restored_path)
    try:
        assert [event.event_id for event in restored_store.all_events()] == ["e1"]
    finally:
        restored_store.close()
        events.close()
        anchors.close()


def test_stale_backup_is_rejected_and_not_published(tmp_path):
    events, anchors = _stores(tmp_path)
    old = tmp_path / "old.sqlite"
    # Advance the independent anchor, then build an older but internally valid backup.
    events.append(_event("e2", 2))
    anchors.create_anchor(events)
    # Build an intentionally stale but internally valid DB by retaining only the anchored
    # first event from a separate store and then test it against the newer independent anchor.
    stale_store = CommandEventStore(tmp_path / "stale.sqlite")
    stale_store.append(_event("e1"))
    stale_anchors = EventIntegrityAnchorStore(tmp_path / "stale-anchors.sqlite")
    stale_anchors.create_anchor(stale_store)
    EventLogBackupManager.create_backup(stale_store, stale_anchors, old)
    with pytest.raises(RuntimeError, match="restore verification failed"):
        EventLogBackupManager.restore_backup(old, tmp_path / "should-not-exist.sqlite", anchors)
    assert not (tmp_path / "should-not-exist.sqlite").exists()
    events.close()
    anchors.close()
    stale_store.close()
    stale_anchors.close()


def test_tampered_backup_fails_verification_and_restore(tmp_path):
    events, anchors = _stores(tmp_path)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(events, anchors, backup)
    connection = sqlite3.connect(str(backup))
    try:
        connection.execute("UPDATE command_events SET payload_json = ? WHERE event_id = ?", ('{"value":999}', "e1"))
        connection.commit()
    finally:
        connection.close()

    assessment = EventLogBackupManager.verify_backup(backup, anchors)
    assert assessment.status is EventLogTrustStatus.DAMAGED
    with pytest.raises(RuntimeError, match="restore verification failed"):
        EventLogBackupManager.restore_backup(backup, tmp_path / "restore-failed.sqlite", anchors)
    assert not (tmp_path / "restore-failed.sqlite").exists()
    events.close()
    anchors.close()


def test_missing_anchor_blocks_backup_creation(tmp_path):
    events = CommandEventStore(tmp_path / "events.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    events.append(_event("e1"))
    with pytest.raises(RuntimeError, match="backup verification failed"):
        EventLogBackupManager.create_backup(events, anchors, tmp_path / "untrusted.sqlite")
    assert not (tmp_path / "untrusted.sqlite").exists()
    events.close()
    anchors.close()


def test_existing_restore_destination_is_never_overwritten(tmp_path):
    events, anchors = _stores(tmp_path)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(events, anchors, backup)
    destination = tmp_path / "existing.sqlite"
    destination.write_bytes(b"keep-me")
    with pytest.raises(FileExistsError):
        EventLogBackupManager.restore_backup(backup, destination, anchors)
    assert destination.read_bytes() == b"keep-me"
    events.close()
    anchors.close()
