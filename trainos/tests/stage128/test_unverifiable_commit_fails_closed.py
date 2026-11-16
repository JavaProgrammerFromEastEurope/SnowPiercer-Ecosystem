"""A COMMIT exception plus unavailable verification must never be reported as success."""
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore, RecoveryAttemptBlocked, RecoveryAttemptStatus,
)


class _FailBeforeCommit:
    """Simulate a driver COMMIT error before durability is established."""

    def __init__(self, connection):
        self.connection = connection
        self.raised = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.raised = True
        raise sqlite3.OperationalError("simulated COMMIT I/O failure")


def _make_verification_unavailable(store, tmp_path):
    """Point only the resolver's fresh connection at a path that cannot be opened."""
    original_path = store.database_path
    store.database_path = str(tmp_path / "missing-parent" / "unavailable.sqlite")
    return original_path


def test_unverifiable_finish_commit_preserves_original_error_and_in_progress_row(tmp_path):
    database = tmp_path / "finish-unverifiable.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    initial = store.begin_attempt("stage128-finish", "stage128 commit verification failure")
    raw_connection = store._connection
    failing = _FailBeforeCommit(raw_connection)
    store._connection = failing
    original_path = _make_verification_unavailable(store, tmp_path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="simulated COMMIT I/O failure"):
            store.finish_success(
                initial.attempt_key, owner_run_id=initial.owner_run_id,
                fencing_token=initial.fencing_token,
            )
        assert failing.raised
        assert not raw_connection.in_transaction
    finally:
        store._connection = raw_connection
        store.database_path = original_path
        store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        durable = restarted.get(initial.attempt_key)
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.IN_PROGRESS
        assert durable.attempt_count == 1
        assert durable.owner_run_id == initial.owner_run_id
        assert durable.fencing_token == initial.fencing_token
        assert durable.lease_expires_at == initial.lease_expires_at
    finally:
        restarted.close()


def test_unverifiable_retry_authorization_commit_leaves_failed_state(tmp_path):
    database = tmp_path / "retry-unverifiable.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    initial = store.begin_attempt("stage128-retry", "stage128 retry commit verification failure")
    failed = store.finish_failure(
        initial.attempt_key, "controlled failure", owner_run_id=initial.owner_run_id,
        fencing_token=initial.fencing_token,
    )
    raw_connection = store._connection
    failing = _FailBeforeCommit(raw_connection)
    store._connection = failing
    original_path = _make_verification_unavailable(store, tmp_path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="simulated COMMIT I/O failure"):
            store.authorize_retry(
                initial.attempt_key, operator="stage128-operator", reason="reviewed retry",
            )
        assert failing.raised
        assert not raw_connection.in_transaction
    finally:
        store._connection = raw_connection
        store.database_path = original_path
        store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        durable = restarted.get(initial.attempt_key)
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.FAILED
        assert durable.attempt_count == failed.attempt_count == 1
        assert durable.max_attempts == failed.max_attempts
        assert durable.fencing_token == failed.fencing_token
        assert durable.authorized_by is None
        assert durable.authorization_reason is None
        assert durable.last_error == "controlled failure"
        with pytest.raises(RecoveryAttemptBlocked, match="authorize retry explicitly"):
            restarted.begin_attempt(initial.attempt_key, "must require explicit authorization")
        unchanged = restarted.get(initial.attempt_key)
        assert unchanged is not None
        assert unchanged.status is RecoveryAttemptStatus.FAILED
        assert unchanged.attempt_count == 1
    finally:
        restarted.close()
