from tests.sqlite_resource_helpers import managed_sqlite_connection
"""A lost COMMIT acknowledgement is not success if any durable field differs."""
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _CommitThenMutateAndLoseAcknowledgement:
    """Simulate a durable commit followed by an unexpected competing DB mutation."""

    def __init__(self, connection, database_path, mutation_sql, mutation_params=()):
        self.connection = connection
        self.database_path = str(database_path)
        self.mutation_sql = mutation_sql
        self.mutation_params = mutation_params
        self.raised = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        if not self.raised:
            self.raised = True
            # A separate connection ensures the mutation is durable before the
            # store's ambiguous-commit resolver opens its verification connection.
            with managed_sqlite_connection(self.database_path) as competing:
                competing.execute(self.mutation_sql, self.mutation_params)
            raise sqlite3.OperationalError("simulated lost acknowledgement after row mismatch")


def _lose_ack_after_mutation(store, database, mutation_sql, mutation_params, operation):
    raw_connection = store._connection
    wrapper = _CommitThenMutateAndLoseAcknowledgement(
        raw_connection, database, mutation_sql, mutation_params,
    )
    store._connection = wrapper
    try:
        with pytest.raises(
            sqlite3.OperationalError,
            match="simulated lost acknowledgement after row mismatch",
        ):
            operation()
        assert wrapper.raised
        assert not raw_connection.in_transaction
    finally:
        store._connection = raw_connection
        store.close()


def test_finish_transition_mismatch_in_status_does_not_resolve_as_success(tmp_path):
    database = tmp_path / "finish-status-mismatch.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    attempt = store.begin_attempt("finish-mismatch", "test finish")

    _lose_ack_after_mutation(
        store, database,
        "UPDATE recovery_attempts SET status=? WHERE attempt_key=?",
        (RecoveryAttemptStatus.SUCCEEDED.value, attempt.attempt_key),
        lambda: store.finish_failure(
            attempt.attempt_key, "expected failure",
            owner_run_id=attempt.owner_run_id, fencing_token=attempt.fencing_token,
        ),
    )

    reopened = EventLogRecoveryAttemptStore(database)
    # The unexpected durable mutation creates a contradictory terminal row. It
    # must remain available for forensic inspection, but the typed API fails closed.
    with pytest.raises(RecoveryAttemptBlocked, match="inconsistent last_error"):
        reopened.get(attempt.attempt_key)
    raw = reopened._connection.execute(
        "SELECT status,last_error FROM recovery_attempts WHERE attempt_key=?",
        (attempt.attempt_key,),
    ).fetchone()
    assert tuple(raw) == (RecoveryAttemptStatus.SUCCEEDED.value, "expected failure")
    reopened.close()


def test_begin_transition_mismatch_in_fencing_token_does_not_resolve_as_success(tmp_path):
    database = tmp_path / "begin-token-mismatch.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt("begin-mismatch", "first", checkpoint_fingerprint="cp-v1")
    store.finish_failure(
        first.attempt_key, "first failed",
        owner_run_id=first.owner_run_id, fencing_token=first.fencing_token,
    )
    store.authorize_retry(
        first.attempt_key, operator="operator", reason="reviewed", checkpoint_fingerprint="cp-v1",
    )

    _lose_ack_after_mutation(
        store, database,
        "UPDATE recovery_attempts SET fencing_token=? WHERE attempt_key=?",
        (77, first.attempt_key),
        lambda: store.begin_attempt(
            first.attempt_key, "retry", checkpoint_fingerprint="cp-v1",
        ),
    )

    reopened = EventLogRecoveryAttemptStore(database)
    # The mismatch remains durable but is now also rejected as a corrupt row
    # by Stage 133's invariant validation.
    with pytest.raises(RecoveryAttemptBlocked, match="inconsistent fencing token"):
        reopened.get(first.attempt_key)
    raw = reopened._connection.execute(
        "SELECT status, attempt_count, fencing_token FROM recovery_attempts WHERE attempt_key=?",
        (first.attempt_key,),
    ).fetchone()
    assert tuple(raw) == (RecoveryAttemptStatus.IN_PROGRESS.value, 2, 77)
    reopened.close()


def test_retry_authorization_mismatch_in_checkpoint_does_not_resolve_as_success(tmp_path):
    database = tmp_path / "authorization-checkpoint-mismatch.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt("auth-mismatch", "first", checkpoint_fingerprint="cp-v1")
    store.finish_failure(
        first.attempt_key, "first failed",
        owner_run_id=first.owner_run_id, fencing_token=first.fencing_token,
    )

    _lose_ack_after_mutation(
        store, database,
        "UPDATE recovery_attempts SET checkpoint_fingerprint=? WHERE attempt_key=?",
        ("cp-tampered", first.attempt_key),
        lambda: store.authorize_retry(
            first.attempt_key, operator="operator", reason="reviewed", checkpoint_fingerprint="cp-v1",
        ),
    )

    reopened = EventLogRecoveryAttemptStore(database)
    row = reopened.get(first.attempt_key)
    assert row is not None
    assert row.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    assert row.authorized_by == "operator"
    assert row.checkpoint_fingerprint == "cp-tampered"
    reopened.close()
