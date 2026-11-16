from tests.sqlite_resource_helpers import managed_sqlite_connection
"""Stage 97 integration bench for event-log trust and recovery invariants."""
from datetime import datetime, timezone
import sqlite3

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogRecoveryGate,
    EventLogStartupRecovery, EventLogTrustStatus, RecoveryAttemptStatus,
    StartupRecoveryStatus,
)


def _event(event_id: str, sequence_value: int) -> CommandEvent:
    return CommandEvent(
        event_id=event_id,
        command_id="stage97-integration",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 10, 21, tzinfo=timezone.utc),
        payload={"sequence_value": sequence_value},
    )


def _fixture(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event("event-1", 1))
    active.append(_event("event-2", 2))
    anchors.create_anchor(active)
    backup = tmp_path / "verified-backup.sqlite"
    backup_assessment = EventLogBackupManager.create_backup(active, anchors, backup)
    assert backup_assessment.trusted_for_read
    with managed_sqlite_connection(active.database_path) as connection:
        connection.execute(
            "UPDATE command_events SET payload_json = ? WHERE event_id = ?",
            ('{"sequence_value":999}', "event-1"),
        )
    return active, anchors, backup


def test_integrated_recovery_restores_candidate_but_never_promotes_active(tmp_path):
    active, anchors, backup = _fixture(tmp_path)
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    candidate = tmp_path / "recovery-candidate.sqlite"

    active_before = active.database_path
    active_assessment = EventLogRecoveryGate.assess(active, anchors)
    assert active_assessment.status is EventLogTrustStatus.DAMAGED
    with pytest.raises(RuntimeError):
        EventLogRecoveryGate.require_verified(active, anchors)

    result = EventLogStartupRecovery.run(
        active_before, anchors, backup_path=backup,
        recovery_destination_path=candidate,
        recovery_attempt_store=journal, recovery_attempt_key="boot-2026-10-21",
    )

    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    assert result.recovery_path == str(candidate.resolve())
    assert result.assessment is not None and result.assessment.trusted_for_read
    assert journal.get("boot-2026-10-21").status is RecoveryAttemptStatus.SUCCEEDED
    assert EventLogBackupManager.verify_backup(candidate, anchors).trusted_for_read

    # The verified copy is prepared separately. The damaged active DB remains untouched.
    with managed_sqlite_connection(active_before) as connection:
        active_payload = connection.execute(
            "SELECT payload_json FROM command_events WHERE event_id='event-1'"
        ).fetchone()[0]
    assert active_payload == '{"sequence_value":999}'
    reopened_active = CommandEventStore(active_before)
    try:
        assert EventLogRecoveryGate.assess(reopened_active, anchors).status is EventLogTrustStatus.DAMAGED
    finally:
        reopened_active.close()

    active.close()
    anchors.close()
    journal.close()


def test_tampered_backup_is_blocked_and_journal_records_failure(tmp_path):
    active, anchors, backup = _fixture(tmp_path)
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    candidate = tmp_path / "candidate.sqlite"

    # Replace the backup with invalid bytes before recovery starts; the fingerprint
    # can be computed, but SQLite validation must fail closed before publication.
    backup.write_bytes(b"not a sqlite backup")
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=candidate,
        recovery_attempt_store=journal, recovery_attempt_key="tampered-backup",
    )

    assert result.status is StartupRecoveryStatus.BLOCKED
    assert result.recovery_path is None
    assert not candidate.exists()
    assert result.findings[-1]["code"] == "recovery_candidate_rejected"
    attempt = journal.get("tampered-backup")
    assert attempt.status is RecoveryAttemptStatus.FAILED
    assert attempt.last_error

    active.close()
    anchors.close()
    journal.close()


def test_missing_anchor_never_makes_active_log_trusted_or_ready(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    active.append(_event("event-1", 1))
    anchors = EventIntegrityAnchorStore(tmp_path / "empty-anchors.sqlite")

    assessment = EventLogRecoveryGate.assess(active, anchors)
    assert assessment.status is EventLogTrustStatus.INSUFFICIENT_DATA
    assert not assessment.trusted_for_read
    result = EventLogStartupRecovery.run(active.database_path, anchors)
    assert result.status is StartupRecoveryStatus.RECOVERY_REQUIRED
    assert result.assessment is not None
    assert not result.assessment.trusted_for_read

    active.close()
    anchors.close()
