from tests.sqlite_resource_helpers import managed_sqlite_connection
"""Stage 103: published candidates are not reconciled while ownership is live/unknown."""
from datetime import datetime, timezone
import sqlite3

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery,
    RecoveryAttemptStatus, StartupRecoveryStatus,
)


def _event() -> CommandEvent:
    return CommandEvent(
        event_id="stage103-event", command_id="stage103",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 10, 21, tzinfo=timezone.utc),
        payload={"stable": True},
    )


def _setup(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event())
    anchors.create_anchor(active)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(active, anchors, backup)
    with managed_sqlite_connection(active.database_path) as connection:
        connection.execute(
            "UPDATE command_events SET payload_json='damaged' WHERE event_id='stage103-event'"
        )
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    destination = tmp_path / "candidate.sqlite"
    fingerprint = EventLogBackupManager.fingerprint_file(backup)
    attempt = journal.begin_attempt(
        "stage103-owner", "test owner race", checkpoint_fingerprint=fingerprint,
    )
    EventLogBackupManager.restore_backup(backup, destination, anchors)
    return active, anchors, backup, journal, destination, attempt


def test_live_owner_prevents_candidate_reconciliation(tmp_path, monkeypatch):
    active, anchors, backup, journal, destination, attempt = _setup(tmp_path)
    monkeypatch.setattr(EventLogRecoveryAttemptStore, "_pid_is_alive", staticmethod(lambda _pid: True))

    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="stage103-owner",
    )

    current = journal.get("stage103-owner")
    assert result.status is StartupRecoveryStatus.BLOCKED
    assert result.findings[-1]["code"] == "recovery_owner_still_alive_or_unknown"
    assert current.status is RecoveryAttemptStatus.IN_PROGRESS
    assert current.owner_run_id == attempt.owner_run_id
    assert current.fencing_token == attempt.fencing_token
    assert destination.is_file()
    active.close(); anchors.close(); journal.close()


def test_unknown_owner_pid_fails_closed_without_changing_journal(tmp_path):
    active, anchors, backup, journal, destination, attempt = _setup(tmp_path)
    with managed_sqlite_connection(journal.database_path) as connection:
        connection.execute(
            "UPDATE recovery_attempts SET owner_pid=NULL WHERE attempt_key=?",
            ("stage103-owner",),
        )
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="stage103-owner",
    )
    current = journal.get("stage103-owner")
    assert result.status is StartupRecoveryStatus.BLOCKED
    assert result.findings[-1]["code"] == "recovery_owner_still_alive_or_unknown"
    assert current.status is RecoveryAttemptStatus.IN_PROGRESS
    assert current.owner_run_id == attempt.owner_run_id
    assert current.fencing_token == attempt.fencing_token
    active.close(); anchors.close(); journal.close()
