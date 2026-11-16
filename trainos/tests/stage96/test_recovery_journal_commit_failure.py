from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from datetime import datetime, timezone

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery,
    RecoveryAttemptStatus, StartupRecoveryStatus,
)


def _event():
    return CommandEvent(
        event_id="stage96-event", command_id="stage96",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"stage": 96},
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
            "UPDATE command_events SET payload_json='damaged' WHERE event_id='stage96-event'"
        )
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    destination = tmp_path / "candidate.sqlite"
    return active, anchors, backup, journal, destination


def test_journal_commit_failure_preserves_candidate_for_safe_restart_reconciliation(tmp_path, monkeypatch):
    active, anchors, backup, journal, destination = _setup(tmp_path)
    original_finish_success = journal.finish_success

    def fail_once(attempt_key, **kwargs):
        raise sqlite3.OperationalError("simulated journal disk failure")

    monkeypatch.setattr(journal, "finish_success", fail_once)
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="stage96-boot",
    )

    assert result.status is StartupRecoveryStatus.BLOCKED
    assert result.findings[-1]["code"] == "recovery_attempt_journal_update_failed"
    assert destination.is_file()
    assert journal.get("stage96-boot").status is RecoveryAttemptStatus.IN_PROGRESS

    # Simulate restart after the original owner process has exited.
    monkeypatch.setattr(EventLogRecoveryAttemptStore, "_pid_is_alive", staticmethod(lambda _pid: False))
    monkeypatch.setattr(journal, "finish_success", original_finish_success)
    journal.close()
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="stage96-boot",
    )
    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    assert result.findings[-1]["code"] == "recovered_publication_after_interruption"
    assert journal.get("stage96-boot").status is RecoveryAttemptStatus.SUCCEEDED

    active.close()
    anchors.close()
    journal.close()


def test_verified_active_log_does_not_touch_unavailable_backup(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event())
    anchors.create_anchor(active)

    result = EventLogStartupRecovery.run(
        active.database_path, anchors,
        backup_path=tmp_path / "missing-backup.sqlite",
        recovery_destination_path=tmp_path / "candidate.sqlite",
    )

    assert result.status is StartupRecoveryStatus.TRUSTED
    assert not (tmp_path / "candidate.sqlite").exists()
    assert not (tmp_path / "missing-backup.sqlite").exists()
    active.close()
    anchors.close()


def test_anchor_assessment_failure_blocks_candidate_publication(tmp_path, monkeypatch):
    active, anchors, backup, journal, destination = _setup(tmp_path)

    def unavailable_anchor():
        raise sqlite3.DatabaseError("simulated anchor storage failure")

    monkeypatch.setattr(anchors, "latest", unavailable_anchor)
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="stage96-anchor-failure",
    )

    assert result.status is StartupRecoveryStatus.BLOCKED
    assert result.findings[-1]["code"] == "recovery_candidate_rejected"
    assert not destination.exists()
    assert journal.get("stage96-anchor-failure").status is RecoveryAttemptStatus.FAILED

    active.close()
    anchors.close()
    journal.close()
