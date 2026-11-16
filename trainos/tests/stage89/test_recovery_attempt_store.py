from tests.sqlite_resource_helpers import managed_sqlite_connection
from datetime import datetime, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery,
    RecoveryAttemptBlocked, RecoveryAttemptStatus, StartupRecoveryStatus,
)


def _event(event_id: str, value: int = 1) -> CommandEvent:
    return CommandEvent(
        event_id=event_id, command_id="stage89", event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"value": value},
    )


def _trusted(tmp_path):
    store = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    store.append(_event("e1"))
    anchors.create_anchor(store)
    return store, anchors


def test_failed_attempt_requires_explicit_retry_authorization(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    first = journal.begin_attempt("boot-1", "restore after corruption")
    assert first.attempt_count == 1
    first = journal.get("boot-1")
    failed = journal.finish_failure("boot-1", "invalid backup", owner_run_id=first.owner_run_id, fencing_token=first.fencing_token)
    assert failed.status is RecoveryAttemptStatus.FAILED
    with pytest.raises(RecoveryAttemptBlocked):
        journal.begin_attempt("boot-1", "retry")
    authorized = journal.authorize_retry("boot-1", operator="operator-1", reason="backup replaced")
    assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    second = journal.begin_attempt("boot-1", "retry after approval")
    assert second.status is RecoveryAttemptStatus.IN_PROGRESS
    assert second.attempt_count == 2
    journal.close()


def test_interrupted_attempt_is_marked_failed_and_blocked(tmp_path):
    path = tmp_path / "attempts.sqlite"
    journal = EventLogRecoveryAttemptStore(path)
    journal.begin_attempt("boot-2", "restore")
    journal.close()  # simulate process termination before completion
    # Simulate that the prior owner belongs to a different, terminated process.
    import sqlite3
    with managed_sqlite_connection(path) as conn:
        conn.execute("UPDATE recovery_attempts SET owner_pid = -1 WHERE attempt_key = ?", ("boot-2",))

    restarted = EventLogRecoveryAttemptStore(path)
    # A negative PID is corrupt ownership metadata, not proof that the owner died.
    with pytest.raises(RecoveryAttemptBlocked, match="invalid"):
        restarted.begin_attempt("boot-2", "startup retry")
    state = restarted.get("boot-2")
    assert state.status is RecoveryAttemptStatus.IN_PROGRESS
    assert state.owner_pid == -1
    restarted.close()


def test_successful_attempt_cannot_be_repeated_with_same_key(tmp_path):
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    attempt = journal.begin_attempt("boot-3", "restore")
    journal.finish_success("boot-3", owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token)
    with pytest.raises(RecoveryAttemptBlocked, match="already succeeded"):
        journal.begin_attempt("boot-3", "repeat")
    journal.close()


def test_startup_recovery_journals_success(tmp_path):
    store, anchors = _trusted(tmp_path)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(store, anchors, backup)
    # Corrupt the active log so startup must prepare the verified backup.
    import sqlite3
    with managed_sqlite_connection(store.database_path) as conn:
        conn.execute("UPDATE command_events SET payload_json='{}' WHERE event_id='e1'")
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    result = EventLogStartupRecovery.run(
        store.database_path, anchors, backup_path=backup,
        recovery_destination_path=tmp_path / "candidate.sqlite",
        recovery_attempt_store=journal, recovery_attempt_key="boot-4",
    )
    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    assert journal.get("boot-4").status is RecoveryAttemptStatus.SUCCEEDED
    store.close(); anchors.close(); journal.close()


def test_startup_failure_is_durable_and_next_retry_is_blocked(tmp_path):
    store, anchors = _trusted(tmp_path)
    stale_store = CommandEventStore(tmp_path / "stale.sqlite")
    stale_anchors = EventIntegrityAnchorStore(tmp_path / "stale-anchors.sqlite")
    stale_store.append(_event("old"))
    stale_anchors.create_anchor(stale_store)
    backup = tmp_path / "stale-backup.sqlite"
    EventLogBackupManager.create_backup(stale_store, stale_anchors, backup)
    store.append(_event("new", 2)); anchors.create_anchor(store)
    import sqlite3
    with managed_sqlite_connection(store.database_path) as conn:
        conn.execute("UPDATE command_events SET payload_json='{}' WHERE event_id='e1'")
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    kwargs = dict(
        active_database_path=store.database_path, anchor_store=anchors,
        backup_path=backup, recovery_destination_path=tmp_path / "candidate.sqlite",
        recovery_attempt_store=journal, recovery_attempt_key="boot-5",
    )
    first = EventLogStartupRecovery.run(**kwargs)
    assert first.status is StartupRecoveryStatus.BLOCKED
    assert journal.get("boot-5").status is RecoveryAttemptStatus.FAILED
    second = EventLogStartupRecovery.run(**kwargs)
    assert second.status is StartupRecoveryStatus.BLOCKED
    assert second.findings[-1]["code"] == "recovery_attempt_blocked"
    store.close(); anchors.close(); stale_store.close(); stale_anchors.close(); journal.close()
