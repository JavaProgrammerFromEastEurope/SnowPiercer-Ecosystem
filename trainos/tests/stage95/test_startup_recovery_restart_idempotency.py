from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from datetime import datetime, timezone

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery,
    RecoveryAttemptStatus, StartupRecoveryStatus,
)


def _event(event_id: str) -> CommandEvent:
    return CommandEvent(
        event_id=event_id, command_id="stage95",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"stage": 95},
    )


def _prepare(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event("event-1"))
    anchors.create_anchor(active)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(active, anchors, backup)
    with managed_sqlite_connection(active.database_path) as connection:
        connection.execute(
            "UPDATE command_events SET payload_json='invalid-payload' WHERE event_id='event-1'"
        )
    return active, anchors, backup


def test_restart_after_success_reuses_verified_candidate_without_republishing(tmp_path):
    active, anchors, backup = _prepare(tmp_path)
    journal_path = tmp_path / "attempts.sqlite"
    destination = tmp_path / "candidate.sqlite"
    journal = EventLogRecoveryAttemptStore(journal_path)
    kwargs = dict(
        active_database_path=active.database_path, anchor_store=anchors,
        backup_path=backup, recovery_destination_path=destination,
        recovery_attempt_store=journal, recovery_attempt_key="stable-boot-key",
    )

    first = EventLogStartupRecovery.run(**kwargs)
    assert first.status is StartupRecoveryStatus.RECOVERY_READY
    assert journal.get("stable-boot-key").status is RecoveryAttemptStatus.SUCCEEDED
    original_candidate_bytes = destination.read_bytes()

    # Simulate a process restart: close and reopen the durable attempt journal.
    journal.close()
    journal = EventLogRecoveryAttemptStore(journal_path)
    kwargs["recovery_attempt_store"] = journal
    second = EventLogStartupRecovery.run(**kwargs)

    assert second.status is StartupRecoveryStatus.RECOVERY_READY
    assert second.recovery_path == str(destination.resolve())
    assert second.findings[-1]["code"] == "reused_verified_recovery_candidate"
    assert destination.read_bytes() == original_candidate_bytes
    assert journal.get("stable-boot-key").status is RecoveryAttemptStatus.SUCCEEDED
    # Recovery remains non-destructive: the active DB is still damaged and not promoted.
    with managed_sqlite_connection(active.database_path) as connection:
        payload = connection.execute(
            "SELECT payload_json FROM command_events WHERE event_id='event-1'"
        ).fetchone()[0]
    assert payload == "invalid-payload"

    active.close()
    anchors.close()
    journal.close()


def test_succeeded_journal_with_tampered_candidate_fails_closed_and_preserves_file(tmp_path):
    active, anchors, backup = _prepare(tmp_path)
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    destination = tmp_path / "candidate.sqlite"
    fingerprint = EventLogBackupManager.fingerprint_file(backup)
    attempt = journal.begin_attempt("stable-boot-key", "first attempt", checkpoint_fingerprint=fingerprint)
    EventLogBackupManager.restore_backup(backup, destination, anchors, expected_sha256=fingerprint)
    journal.finish_success("stable-boot-key", owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token)
    destination.write_bytes(b"tampered candidate")

    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="stable-boot-key",
    )
    assert result.status is StartupRecoveryStatus.BLOCKED
    assert result.findings[-1]["code"] == "recovery_candidate_reconciliation_failed"
    assert destination.read_bytes() == b"tampered candidate"
    assert journal.get("stable-boot-key").status is RecoveryAttemptStatus.SUCCEEDED

    active.close()
    anchors.close()
    journal.close()
