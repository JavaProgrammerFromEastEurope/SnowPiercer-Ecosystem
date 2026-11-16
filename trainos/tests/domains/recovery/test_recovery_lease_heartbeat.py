from contextlib import closing
"""Stage 105: startup recovery renews its lease while long work is in progress."""
from datetime import datetime, timezone
import sqlite3
import time

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery,
    RecoveryAttemptStatus, StartupRecoveryStatus,
)


def _event(event_id: str) -> CommandEvent:
    return CommandEvent(
        event_id=event_id, command_id="stage105-heartbeat",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 10, 21, tzinfo=timezone.utc), payload={"stable": True},
    )


def _setup(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event("event-1"))
    anchors.create_anchor(active)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(active, anchors, backup)
    with closing(sqlite3.connect(active.database_path)) as connection, connection:
        connection.execute("UPDATE command_events SET payload_json='invalid' WHERE event_id='event-1'")
    return active, anchors, backup


def test_startup_renews_lease_during_slow_restore(tmp_path, monkeypatch):
    active, anchors, backup = _setup(tmp_path)
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    candidate = tmp_path / "candidate.sqlite"
    original_restore = EventLogBackupManager.restore_backup
    original_renew = journal.renew_lease
    renewals = []

    def record_renewal(*args, **kwargs):
        renewals.append(time.monotonic())
        return original_renew(*args, **kwargs)

    def slow_restore(*args, **kwargs):
        time.sleep(0.22)  # Longer than the lease, but shorter than a heartbeat cadence sequence.
        return original_restore(*args, **kwargs)

    monkeypatch.setattr(journal, "renew_lease", record_renewal)
    monkeypatch.setattr(EventLogBackupManager, "restore_backup", slow_restore)
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=candidate, recovery_attempt_store=journal,
        recovery_attempt_key="heartbeat-success", recovery_lease_seconds=0.09,
        recovery_heartbeat_interval_seconds=0.02,
    )

    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    assert len(renewals) >= 2
    assert journal.get("heartbeat-success").status is RecoveryAttemptStatus.SUCCEEDED
    active.close()
    anchors.close()
    journal.close()


def test_heartbeat_failure_blocks_result_and_preserves_in_progress_journal(tmp_path, monkeypatch):
    active, anchors, backup = _setup(tmp_path)
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    candidate = tmp_path / "candidate.sqlite"
    original_restore = EventLogBackupManager.restore_backup

    def fail_renewal(*_args, **_kwargs):
        raise OSError("simulated heartbeat storage failure")

    def slow_restore(*args, **kwargs):
        time.sleep(0.08)
        return original_restore(*args, **kwargs)

    monkeypatch.setattr(journal, "renew_lease", fail_renewal)
    monkeypatch.setattr(EventLogBackupManager, "restore_backup", slow_restore)
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=candidate, recovery_attempt_store=journal,
        recovery_attempt_key="heartbeat-failure", recovery_lease_seconds=0.3,
        recovery_heartbeat_interval_seconds=0.02,
    )

    assert result.status is StartupRecoveryStatus.BLOCKED
    assert result.findings[-1]["code"] == "recovery_lease_heartbeat_failed"
    assert candidate.is_file()  # Candidate is preserved, but not declared ready.
    attempt = journal.get("heartbeat-failure")
    assert attempt.status is RecoveryAttemptStatus.IN_PROGRESS
    assert attempt.owner_run_id is not None
    active.close()
    anchors.close()
    journal.close()


def test_invalid_heartbeat_intervals_are_rejected_before_starting_attempt(tmp_path):
    active, anchors, backup = _setup(tmp_path)
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    for lease, interval in ((1, 1), (1, 0), (1, float("inf")), (True, 0.1)):
        with pytest.raises(ValueError, match="recovery_lease_seconds|heartbeat interval"):
            EventLogStartupRecovery.run(
                active.database_path, anchors, backup_path=backup,
                recovery_destination_path=tmp_path / f"candidate-{lease}-{interval}.sqlite",
                recovery_attempt_store=journal, recovery_attempt_key=f"invalid-{lease}-{interval}",
                recovery_lease_seconds=lease, recovery_heartbeat_interval_seconds=interval,
            )
    assert journal.get("invalid-1-1") is None
    active.close()
    anchors.close()
    journal.close()
