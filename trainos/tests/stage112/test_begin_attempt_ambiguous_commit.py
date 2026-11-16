import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _CommitThenRaiseOnce:
    """Commit durably, then simulate loss of the commit acknowledgement."""

    def __init__(self, connection):
        self.connection = connection
        self.raise_once = True

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        if self.raise_once:
            self.raise_once = False
            raise sqlite3.OperationalError("simulated lost COMMIT acknowledgement")


class _RaiseBeforeCommitOnce:
    """Simulate a commit call failing before delegating to SQLite."""

    def __init__(self, connection):
        self.connection = connection
        self.raise_once = True

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        if self.raise_once:
            self.raise_once = False
            raise sqlite3.OperationalError("simulated pre-commit failure")
        self.connection.commit()


def test_new_attempt_resolves_lost_commit_ack_and_restart_does_not_duplicate(tmp_path):
    database = tmp_path / "attempts.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    raw = store._connection
    store._connection = _CommitThenRaiseOnce(raw)

    started = store.begin_attempt(
        "ambiguous-create", "stage112 initial attempt", checkpoint_fingerprint="sha256:abc",
    )

    assert started.status is RecoveryAttemptStatus.IN_PROGRESS
    assert started.attempt_count == 1
    assert started.owner_run_id
    assert started.fencing_token == 1
    store._connection = raw
    store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    durable = restarted.get("ambiguous-create")
    assert durable == started
    with pytest.raises(RecoveryAttemptBlocked, match="already in progress"):
        restarted.begin_attempt("ambiguous-create", "must not duplicate")
    after_retry = restarted.get("ambiguous-create")
    assert after_retry.attempt_count == 1
    assert after_retry.owner_run_id == started.owner_run_id
    assert after_retry.fencing_token == started.fencing_token
    restarted.close()


def test_authorized_retry_resolves_lost_commit_ack_without_double_increment(tmp_path):
    database = tmp_path / "retry.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt("retry-key", "first try", max_attempts=3)
    store.finish_failure(
        "retry-key", "injected failure", owner_run_id=first.owner_run_id,
        fencing_token=first.fencing_token,
    )
    store.authorize_retry("retry-key", operator="operator", reason="reviewed")

    raw = store._connection
    store._connection = _CommitThenRaiseOnce(raw)
    second = store.begin_attempt("retry-key", "authorized retry")

    assert second.status is RecoveryAttemptStatus.IN_PROGRESS
    assert second.attempt_count == 2
    assert second.fencing_token == first.fencing_token + 1
    assert second.owner_run_id != first.owner_run_id
    assert second.authorized_by is None
    assert second.authorization_reason is None
    store._connection = raw
    store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    durable = restarted.get("retry-key")
    assert durable == second
    with pytest.raises(RecoveryAttemptBlocked, match="already in progress"):
        restarted.begin_attempt("retry-key", "duplicate after restart")
    assert restarted.get("retry-key").attempt_count == 2
    restarted.close()


def test_precommit_failure_does_not_create_attempt_and_can_be_retried(tmp_path):
    database = tmp_path / "precommit.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    raw = store._connection
    store._connection = _RaiseBeforeCommitOnce(raw)

    with pytest.raises(sqlite3.OperationalError, match="pre-commit failure"):
        store.begin_attempt("not-created", "stage112 failure")
    assert not raw.in_transaction
    assert store.get("not-created") is None

    store._connection = raw
    result = store.begin_attempt("not-created", "safe retry")
    assert result.status is RecoveryAttemptStatus.IN_PROGRESS
    assert result.attempt_count == 1
    store.close()
