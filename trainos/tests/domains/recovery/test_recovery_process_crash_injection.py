"""Real subprocess crash-injection tests for durable startup recovery windows."""
from __future__ import annotations
from contextlib import closing

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery,
    RecoveryAttemptBlocked, RecoveryAttemptStatus, StartupRecoveryStatus,
)


def _event() -> CommandEvent:
    return CommandEvent(
        event_id="stage107-event", command_id="stage107",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"stage": 107},
    )


def _setup(tmp_path: Path):
    active = CommandEventStore(tmp_path / "active.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    active.append(_event())
    anchors.create_anchor(active)
    backup = tmp_path / "backup.sqlite"
    EventLogBackupManager.create_backup(active, anchors, backup)
    import sqlite3
    with closing(sqlite3.connect(active.database_path)) as connection, connection:
        connection.execute("UPDATE command_events SET payload_json='damaged' WHERE event_id='stage107-event'")
    journal = EventLogRecoveryAttemptStore(tmp_path / "attempts.sqlite")
    return active, anchors, backup, journal, tmp_path / "candidate.sqlite"


def _crash_worker(root: Path, mode: str, key: str) -> subprocess.CompletedProcess[str]:
    # The child uses real SQLite connections and os._exit(), bypassing finally blocks
    # and Python cleanup to approximate abrupt process death at a durability boundary.
    script = r'''
import os, sys
from kernel.command.events import EventIntegrityAnchorStore, EventLogBackupManager, EventLogRecoveryAttemptStore, EventLogStartupRecovery
root, mode, key = sys.argv[1:]
anchors = EventIntegrityAnchorStore(root + "/anchors.sqlite")
journal = EventLogRecoveryAttemptStore(root + "/attempts.sqlite")
if mode == "before_publish":
    EventLogBackupManager.restore_backup = staticmethod(lambda *a, **k: os._exit(71))
elif mode == "after_publish_before_commit":
    journal.finish_success = lambda *a, **k: os._exit(72)
elif mode == "after_commit_before_return":
    original = journal.finish_success
    def commit_then_crash(*a, **k):
        original(*a, **k)
        os._exit(73)
    journal.finish_success = commit_then_crash
EventLogStartupRecovery.run(
    root + "/active.sqlite", anchors,
    backup_path=root + "/backup.sqlite", recovery_destination_path=root + "/candidate.sqlite",
    recovery_attempt_store=journal, recovery_attempt_key=key,
)
os._exit(0)
'''
    env = os.environ.copy()
    project_root = str(Path(__file__).resolve().parents[3])
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", script, str(root), mode, key],
        cwd=project_root, env=env, text=True, capture_output=True, timeout=15,
    )


def _close(active, anchors, journal):
    active.close()
    anchors.close()
    journal.close()


def test_process_crash_before_candidate_publication_requires_explicit_retry(tmp_path):
    active, anchors, backup, journal, destination = _setup(tmp_path)
    child = _crash_worker(tmp_path, "before_publish", "crash-before-publish")
    assert child.returncode == 71, child.stderr
    assert not destination.exists()
    attempt = journal.get("crash-before-publish")
    assert attempt is not None and attempt.status is RecoveryAttemptStatus.IN_PROGRESS

    with pytest.raises(RecoveryAttemptBlocked, match="interrupted"):
        journal.begin_attempt("crash-before-publish", "restart after crash")
    assert journal.get("crash-before-publish").status is RecoveryAttemptStatus.FAILED
    journal.authorize_retry(
        "crash-before-publish", operator="stage107-test", reason="reviewed crash before publication",
    )
    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="crash-before-publish",
    )
    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    assert destination.is_file()
    assert journal.get("crash-before-publish").status is RecoveryAttemptStatus.SUCCEEDED
    _close(active, anchors, journal)


def test_process_crash_after_publication_before_journal_commit_reconciles_candidate(tmp_path):
    active, anchors, backup, journal, destination = _setup(tmp_path)
    child = _crash_worker(tmp_path, "after_publish_before_commit", "crash-after-publish")
    assert child.returncode == 72, child.stderr
    assert destination.is_file()
    assert journal.get("crash-after-publish").status is RecoveryAttemptStatus.IN_PROGRESS

    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="crash-after-publish",
    )
    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    assert result.findings[-1]["code"] == "recovered_publication_after_interruption"
    assert journal.get("crash-after-publish").status is RecoveryAttemptStatus.SUCCEEDED
    _close(active, anchors, journal)


def test_process_crash_after_success_commit_reuses_verified_candidate_idempotently(tmp_path):
    active, anchors, backup, journal, destination = _setup(tmp_path)
    child = _crash_worker(tmp_path, "after_commit_before_return", "crash-after-commit")
    assert child.returncode == 73, child.stderr
    assert destination.is_file()
    assert journal.get("crash-after-commit").status is RecoveryAttemptStatus.SUCCEEDED

    result = EventLogStartupRecovery.run(
        active.database_path, anchors, backup_path=backup,
        recovery_destination_path=destination, recovery_attempt_store=journal,
        recovery_attempt_key="crash-after-commit",
    )
    assert result.status is StartupRecoveryStatus.RECOVERY_READY
    assert result.findings[-1]["code"] == "reused_verified_recovery_candidate"
    assert journal.get("crash-after-commit").status is RecoveryAttemptStatus.SUCCEEDED
    _close(active, anchors, journal)
