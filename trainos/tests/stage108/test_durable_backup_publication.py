from datetime import datetime, timezone
import os
import sqlite3

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager,
)


def _event(event_id: str) -> CommandEvent:
    return CommandEvent(
        event_id=event_id,
        command_id="stage108",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        payload={"event": event_id},
    )


def _stores(tmp_path):
    events = CommandEventStore(tmp_path / "events.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    events.append(_event("e1"))
    anchors.create_anchor(events)
    return events, anchors


def test_file_flush_failure_prevents_candidate_publication(tmp_path, monkeypatch):
    events, anchors = _stores(tmp_path)
    backup = tmp_path / "backup.sqlite"

    def fail_flush(_path):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(EventLogBackupManager, "_fsync_file", staticmethod(fail_flush))
    with pytest.raises(OSError, match="fsync failure"):
        EventLogBackupManager.create_backup(events, anchors, backup)

    assert not backup.exists()
    assert not list(tmp_path.glob(".backup.sqlite.*.tmp"))
    events.close()
    anchors.close()


def test_directory_flush_failure_leaves_candidate_for_reconciliation(tmp_path, monkeypatch):
    events, anchors = _stores(tmp_path)
    backup = tmp_path / "backup.sqlite"
    original = EventLogBackupManager._fsync_directory
    calls = 0

    def fail_first_directory_flush(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated directory fsync failure")
        return original(path)

    monkeypatch.setattr(
        EventLogBackupManager, "_fsync_directory", staticmethod(fail_first_directory_flush)
    )
    with pytest.raises(OSError, match="directory fsync failure"):
        EventLogBackupManager.create_backup(events, anchors, backup)

    # Linking already happened. A reported failure must not delete or replace the
    # candidate; startup recovery can independently verify it on the next run.
    assert backup.is_file()
    assert EventLogBackupManager.verify_backup(backup, anchors).trusted_for_read
    events.close()
    anchors.close()


def test_source_change_during_copy_is_rejected_before_publication(tmp_path, monkeypatch):
    events, anchors = _stores(tmp_path)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(events, anchors, backup)
    destination = tmp_path / "candidate.sqlite"
    original_copy = EventLogBackupManager._copy_sqlite
    changed = False

    def copy_then_change_source(source, target):
        nonlocal changed
        original_copy(source, target)
        if not changed:
            changed = True
            with source.open("ab") as handle:
                handle.write(b"changed-after-copy")
                handle.flush()
                os.fsync(handle.fileno())

    monkeypatch.setattr(EventLogBackupManager, "_copy_sqlite", staticmethod(copy_then_change_source))
    with pytest.raises(RuntimeError, match="changed while recovery candidate was being copied"):
        EventLogBackupManager.restore_backup(backup, destination, anchors)

    assert not destination.exists()
    assert not list(tmp_path.glob(".candidate.sqlite.*.restore"))
    events.close()
    anchors.close()
