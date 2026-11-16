import errno
from datetime import datetime, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager,
)


def _stores(tmp_path):
    events = CommandEventStore(tmp_path / "events.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    events.append(CommandEvent(
        event_id="stage109-event",
        command_id="stage109-command",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        payload={"stage": 109},
    ))
    anchors.create_anchor(events)
    return events, anchors


def test_enospc_during_backup_capture_does_not_publish_or_leave_temp(tmp_path, monkeypatch):
    events, anchors = _stores(tmp_path)
    target = tmp_path / "backup.sqlite"

    def disk_full(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "simulated no space left on device")

    monkeypatch.setattr(EventLogBackupManager, "_assess_database", staticmethod(disk_full))
    with pytest.raises(OSError) as error:
        EventLogBackupManager.create_backup(events, anchors, target)

    assert error.value.errno == errno.ENOSPC
    assert not target.exists()
    assert not list(tmp_path.glob(".backup.sqlite.*.tmp"))
    events.close()
    anchors.close()


def test_restore_copy_io_failure_does_not_publish_candidate_or_leave_temp(tmp_path, monkeypatch):
    events, anchors = _stores(tmp_path)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(events, anchors, backup)
    target = tmp_path / "candidate.sqlite"

    def interrupted_copy(_source, destination):
        destination.write_bytes(b"partial")
        raise OSError(errno.EIO, "simulated interrupted storage write")

    monkeypatch.setattr(EventLogBackupManager, "_copy_sqlite", staticmethod(interrupted_copy))
    with pytest.raises(OSError) as error:
        EventLogBackupManager.restore_backup(backup, target, anchors)

    assert error.value.errno == errno.EIO
    assert not target.exists()
    assert not list(tmp_path.glob(".candidate.sqlite.*.restore"))
    events.close()
    anchors.close()


def test_no_clobber_publication_preserves_racing_destination(tmp_path):
    temporary = tmp_path / "complete.tmp"
    target = tmp_path / "candidate.sqlite"
    temporary.write_bytes(b"verified candidate")
    target.write_bytes(b"another process published this")

    with pytest.raises(FileExistsError):
        EventLogBackupManager._publish_no_clobber(temporary, target)

    assert target.read_bytes() == b"another process published this"
    assert temporary.read_bytes() == b"verified candidate"


def test_backup_verification_failure_leaves_no_trusted_backup(tmp_path, monkeypatch):
    events, anchors = _stores(tmp_path)
    target = tmp_path / "backup.sqlite"

    def verification_failure(*_args, **_kwargs):
        raise RuntimeError("simulated backup verification failure")

    monkeypatch.setattr(EventLogBackupManager, "_assess_database", staticmethod(verification_failure))
    with pytest.raises(RuntimeError, match="backup verification failure"):
        EventLogBackupManager.create_backup(events, anchors, target)

    assert not target.exists()
    assert not list(tmp_path.glob(".backup.sqlite.*.tmp"))
    events.close()
    anchors.close()
