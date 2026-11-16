from datetime import datetime, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager,
)


def _event():
    return CommandEvent(
        event_id="race-event", command_id="stage92",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"stage": 92},
    )


def _stores(tmp_path):
    events = CommandEventStore(tmp_path / "events.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    events.append(_event())
    anchors.create_anchor(events)
    return events, anchors


@pytest.mark.parametrize("operation", ["backup", "restore"])
def test_competing_destination_created_at_publish_is_never_overwritten(
    tmp_path, monkeypatch, operation,
):
    events, anchors = _stores(tmp_path)
    backup = tmp_path / "checkpoint.sqlite"
    EventLogBackupManager.create_backup(events, anchors, backup)
    destination = tmp_path / ("racing-backup.sqlite" if operation == "backup" else "racing-restore.sqlite")
    original_publish = EventLogBackupManager._publish_no_clobber
    competitor_bytes = b"created-by-competing-writer"

    def race_publish(temporary_path, target_path):
        assert target_path == destination
        target_path.write_bytes(competitor_bytes)
        return original_publish(temporary_path, target_path)

    monkeypatch.setattr(EventLogBackupManager, "_publish_no_clobber", staticmethod(race_publish))
    with pytest.raises(FileExistsError):
        if operation == "backup":
            EventLogBackupManager.create_backup(events, anchors, destination)
        else:
            EventLogBackupManager.restore_backup(backup, destination, anchors)
    assert destination.read_bytes() == competitor_bytes
    events.close()
    anchors.close()


def test_no_clobber_publisher_keeps_existing_target_and_temporary_file(tmp_path):
    temporary = tmp_path / "complete.tmp"
    target = tmp_path / "target.sqlite"
    temporary.write_bytes(b"verified candidate")
    target.write_bytes(b"existing owner")

    with pytest.raises(FileExistsError):
        EventLogBackupManager._publish_no_clobber(temporary, target)

    assert target.read_bytes() == b"existing owner"
    assert temporary.read_bytes() == b"verified candidate"
