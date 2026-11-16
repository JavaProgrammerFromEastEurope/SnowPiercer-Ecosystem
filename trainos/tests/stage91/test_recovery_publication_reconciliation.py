from tests.sqlite_resource_helpers import managed_sqlite_connection
from datetime import datetime, timezone

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery,
    RecoveryAttemptStatus, StartupRecoveryStatus,
)


def _event(event_id: str) -> CommandEvent:
    return CommandEvent(
        event_id=event_id, command_id="stage91",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"stage": 91},
    )


def _setup(tmp_path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event("event-1"))
    anchors.create_anchor(active)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(active, anchors, backup)
    # Damage active after the checkpoint so startup enters the recovery path.
    import sqlite3
    with managed_sqlite_connection(active.database_path) as connection:
        connection.execute("UPDATE command_events SET payload_json='{}' WHERE event_id='event-1'")
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    return active, anchors, backup, journal


def test_reconciles_candidate_published_before_success_journal_commit(tmp_path, monkeypatch):
    active, anchors, backup, journal = _setup(tmp_path)
    destination = tmp_path / "candidate.sqlite"
    original = journal.finish_success

    def simulate_process_crash(key, **kwargs):
        # BaseException models abrupt process termination; startup's ordinary
        # exception handler must not swallow it or clean up the published file.
        raise SystemExit("simulated crash after candidate publication")

    monkeypatch.setattr(journal, "finish_success", simulate_process_crash)
    kwargs = dict(
        active_database_path=active.database_path, anchor_store=anchors,
        backup_path=backup, recovery_destination_path=destination,
        recovery_attempt_store=journal, recovery_attempt_key="boot-crash-window",
    )
    try:
        EventLogStartupRecovery.run(**kwargs)
        assert False, "simulated crash should escape"
    except SystemExit as exc:
        assert "simulated crash" in str(exc)
    assert destination.is_file()
    assert journal.get("boot-crash-window").status is RecoveryAttemptStatus.IN_PROGRESS

    monkeypatch.setattr(journal, "finish_success", original)
    # This second invocation models a new process after the original owner exited.
    monkeypatch.setattr(EventLogRecoveryAttemptStore, "_pid_is_alive", staticmethod(lambda _pid: False))
    journal.close()
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    kwargs["recovery_attempt_store"] = journal
    result = EventLogStartupRecovery.run(**kwargs)
    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    assert result.recovery_path == str(destination.resolve())
    assert result.findings[-1]["code"] == "recovered_publication_after_interruption"
    assert journal.get("boot-crash-window").status is RecoveryAttemptStatus.SUCCEEDED
    active.close(); anchors.close(); journal.close()


def test_interrupted_attempt_with_untrusted_existing_candidate_is_blocked(tmp_path, monkeypatch):
    active, anchors, backup, journal = _setup(tmp_path)
    destination = tmp_path / "candidate.sqlite"
    fingerprint = EventLogBackupManager.fingerprint_file(backup)
    journal.begin_attempt("boot-bad-candidate", "test crash", checkpoint_fingerprint=fingerprint)
    destination.write_bytes(b"not a sqlite database")
    monkeypatch.setattr(EventLogRecoveryAttemptStore, "_pid_is_alive", staticmethod(lambda _pid: False))
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="boot-bad-candidate",
    )
    assert result.status is StartupRecoveryStatus.BLOCKED
    assert result.findings[-1]["code"] == "interrupted_publication_reconciliation_failed"
    assert destination.read_bytes() == b"not a sqlite database"
    assert journal.get("boot-bad-candidate").status is RecoveryAttemptStatus.IN_PROGRESS
    active.close(); anchors.close(); journal.close()


def test_interrupted_candidate_from_different_checkpoint_is_blocked(tmp_path, monkeypatch):
    active, anchors, backup, journal = _setup(tmp_path)
    destination = tmp_path / "candidate.sqlite"
    fingerprint = EventLogBackupManager.fingerprint_file(backup)
    journal.begin_attempt("boot-changed-checkpoint", "test crash", checkpoint_fingerprint="0" * 64)
    # A valid candidate is still not enough if the input checkpoint changed.
    EventLogBackupManager.restore_backup(backup, destination, anchors)
    monkeypatch.setattr(EventLogRecoveryAttemptStore, "_pid_is_alive", staticmethod(lambda _pid: False))
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="boot-changed-checkpoint",
    )
    assert result.status is StartupRecoveryStatus.BLOCKED
    assert result.findings[-1]["code"] == "interrupted_publication_reconciliation_failed"
    assert journal.get("boot-changed-checkpoint").checkpoint_fingerprint == "0" * 64
    active.close(); anchors.close(); journal.close()
