from tests.sqlite_resource_helpers import managed_sqlite_connection
from datetime import datetime, timezone
import sqlite3

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery,
    RecoveryAttemptBlocked, RecoveryAttemptStatus, StartupRecoveryStatus,
)


def _event(event_id: str, value: int = 1) -> CommandEvent:
    return CommandEvent(
        event_id=event_id, command_id="stage90", event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"value": value},
    )


def test_retry_authorization_is_bound_to_checkpoint_fingerprint(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    first = journal.begin_attempt("boot", "first", checkpoint_fingerprint="sha256-a", max_attempts=3)
    journal.finish_failure("boot", "bad backup", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token)
    journal.authorize_retry(
        "boot", operator="operator", reason="reviewed backup", checkpoint_fingerprint="sha256-b",
    )
    with pytest.raises(RecoveryAttemptBlocked, match="checkpoint changed"):
        journal.begin_attempt("boot", "retry", checkpoint_fingerprint="sha256-c")
    # A mismatched retry does not consume the authorization; the exact approved input works.
    started = journal.begin_attempt("boot", "retry", checkpoint_fingerprint="sha256-b")
    assert started.attempt_count == 2
    assert started.checkpoint_fingerprint == "sha256-b"
    journal.close()


def test_maximum_attempts_cannot_be_raised_by_retry_caller(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    first = journal.begin_attempt("bounded", "first", checkpoint_fingerprint="sha256-a", max_attempts=2)
    journal.finish_failure("bounded", "first failure", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token)
    journal.authorize_retry("bounded", operator="operator", reason="retry approved")
    second = journal.begin_attempt("bounded", "second", checkpoint_fingerprint="sha256-a", max_attempts=99)
    journal.finish_failure("bounded", "second failure", owner_run_id=second.owner_run_id, fencing_token=second.fencing_token)
    with pytest.raises(RecoveryAttemptBlocked, match="maximum recovery attempts"):
        journal.authorize_retry("bounded", operator="operator", reason="no more automatic retries")
    assert journal.get("bounded").attempt_count == 2
    journal.close()


def test_startup_recovery_records_backup_fingerprint_and_rejects_changed_backup(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event("e1"))
    anchors.create_anchor(active)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(active, anchors, backup)
    with managed_sqlite_connection(active.database_path) as conn:
        conn.execute("UPDATE command_events SET payload_json='{}' WHERE event_id='e1'")
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    kwargs = dict(
        active_database_path=active.database_path, anchor_store=anchors,
        backup_path=backup, recovery_destination_path=tmp_path / "candidate.sqlite",
        recovery_attempt_store=journal, recovery_attempt_key="boot-bound",
    )
    result = EventLogStartupRecovery.run(**kwargs)
    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    recorded = journal.get("boot-bound")
    assert recorded.status is RecoveryAttemptStatus.SUCCEEDED
    assert recorded.checkpoint_fingerprint == EventLogBackupManager.fingerprint_file(backup)
    assert len(recorded.checkpoint_fingerprint) == 64
    active.close(); anchors.close(); journal.close()


def test_restore_rejects_backup_that_does_not_match_authorized_fingerprint(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event("e1"))
    anchors.create_anchor(active)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(active, anchors, backup)
    fingerprint = EventLogBackupManager.fingerprint_file(backup)
    with backup.open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(RuntimeError, match="fingerprint"):
        EventLogBackupManager.restore_backup(
            backup, tmp_path / "candidate.sqlite", anchors, expected_sha256=fingerprint,
        )
    assert not (tmp_path / "candidate.sqlite").exists()
    active.close(); anchors.close()
