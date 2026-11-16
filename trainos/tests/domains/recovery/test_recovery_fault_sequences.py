from contextlib import closing
"""Stage 98 fault-sequence tests for recovery restart boundaries and retries."""
from datetime import datetime, timezone
import sqlite3

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery,
    RecoveryAttemptStatus, StartupRecoveryStatus,
)


def _event(event_id: str) -> CommandEvent:
    return CommandEvent(
        event_id=event_id,
        command_id="stage98-fault-sequence",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 10, 21, tzinfo=timezone.utc),
        payload={"stable": True},
    )


def _setup(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event("event-1"))
    anchors.create_anchor(active)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(active, anchors, backup)
    with closing(sqlite3.connect(active.database_path)) as connection, connection:
        connection.execute(
            "UPDATE command_events SET payload_json='invalid' WHERE event_id='event-1'"
        )
    return active, anchors, backup


def test_backup_change_after_publication_interrupt_blocks_reconciliation(tmp_path, monkeypatch):
    active, anchors, backup = _setup(tmp_path)
    journal_path = tmp_path / "attempts.sqlite"
    journal = EventLogRecoveryAttemptStore(journal_path)
    candidate = tmp_path / "candidate.sqlite"
    original_finish = journal.finish_success

    def fail_commit(_attempt_key, **kwargs):
        raise OSError("simulated durable journal commit failure")

    monkeypatch.setattr(journal, "finish_success", fail_commit)
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=candidate, recovery_attempt_store=journal,
        recovery_attempt_key="faulted-boot",
    )
    assert result.status is StartupRecoveryStatus.BLOCKED
    assert candidate.is_file()
    attempt = journal.get("faulted-boot")
    assert attempt.status is RecoveryAttemptStatus.IN_PROGRESS
    recorded_fingerprint = attempt.checkpoint_fingerprint

    # Simulate external modification between crash and restart. Reconciliation must
    # not bless the candidate against a different backup checkpoint.
    backup.write_bytes(b"backup changed after candidate publication")
    journal.close()
    journal = EventLogRecoveryAttemptStore(journal_path)
    # Model a fresh process after the prior owner exited.
    monkeypatch.setattr(EventLogRecoveryAttemptStore, "_pid_is_alive", staticmethod(lambda _pid: False))
    resumed = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=candidate, recovery_attempt_store=journal,
        recovery_attempt_key="faulted-boot",
    )
    assert resumed.status is StartupRecoveryStatus.BLOCKED
    assert resumed.findings[-1]["code"] == "interrupted_publication_reconciliation_failed"
    assert journal.get("faulted-boot").status is RecoveryAttemptStatus.IN_PROGRESS
    assert journal.get("faulted-boot").checkpoint_fingerprint == recorded_fingerprint
    assert candidate.is_file()  # preserved for investigation, never declared ready

    monkeypatch.setattr(journal, "finish_success", original_finish)
    active.close()
    anchors.close()
    journal.close()


def test_retry_after_failure_requires_explicit_new_checkpoint_authorization(tmp_path):
    active, anchors, backup = _setup(tmp_path)
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    candidate = tmp_path / "candidate.sqlite"
    backup.write_bytes(b"initially invalid backup")

    failed = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=candidate, recovery_attempt_store=journal,
        recovery_attempt_key="reviewed-retry", max_recovery_attempts=3,
    )
    assert failed.status is StartupRecoveryStatus.BLOCKED
    assert journal.get("reviewed-retry").status is RecoveryAttemptStatus.FAILED
    assert not candidate.exists()

    # A newly verified backup gets a new fingerprint, but it must be explicitly
    # approved by an operator before the journal will permit retry.
    replacement = tmp_path / "replacement.sqlite"
    # The active database is damaged, so regenerate the original trusted contents
    # in a fresh event store; the anchor validates the deterministic event chain.
    trusted = CommandEventStore(tmp_path / "trusted.sqlite")
    trusted.append(_event("event-1"))
    # Anchor verification binds event content and sequence; this fresh store reproduces
    # the original event chain deterministically for the same event payload.
    EventLogBackupManager.create_backup(trusted, anchors, replacement)
    replacement.replace(backup)
    new_fingerprint = EventLogBackupManager.fingerprint_file(backup)
    authorized = journal.authorize_retry(
        "reviewed-retry", operator="test-operator",
        reason="reviewed replacement backup and fingerprint",
        checkpoint_fingerprint=new_fingerprint,
    )
    assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED

    retried = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=candidate, recovery_attempt_store=journal,
        recovery_attempt_key="reviewed-retry", max_recovery_attempts=3,
    )
    assert retried.status is StartupRecoveryStatus.RECOVERY_READY
    assert journal.get("reviewed-retry").status is RecoveryAttemptStatus.SUCCEEDED
    assert journal.get("reviewed-retry").attempt_count == 2

    active.close()
    anchors.close()
    trusted.close()
    journal.close()
