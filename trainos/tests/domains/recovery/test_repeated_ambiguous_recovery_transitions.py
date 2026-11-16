"""Repeated lost-acknowledgement/restart cycles must preserve journal invariants."""
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _CommitThenLoseAcknowledgement:
    def __init__(self, connection):
        self.connection = connection
        self.raised = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        if not self.raised:
            self.raised = True
            raise sqlite3.OperationalError("simulated lost acknowledgement")


def _run_with_unavailable_verifier(store, database, tmp_path, operation):
    raw_connection = store._connection
    wrapper = _CommitThenLoseAcknowledgement(raw_connection)
    store._connection = wrapper
    original_path = store.database_path
    store.database_path = str(tmp_path / "unavailable" / "journal.sqlite")
    try:
        with pytest.raises(sqlite3.OperationalError, match="simulated lost acknowledgement"):
            operation()
        assert wrapper.raised
        assert not raw_connection.in_transaction
    finally:
        store._connection = raw_connection
        store.database_path = original_path
        store.close()
    return EventLogRecoveryAttemptStore(database)


def test_repeated_lost_acknowledgements_and_restarts_preserve_attempt_history(tmp_path):
    database = tmp_path / "repeated-recovery.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    first = store.begin_attempt(
        "stage130-repeated", "first attempt", checkpoint_fingerprint="checkpoint-v1", max_attempts=3,
    )

    # The first failure is durable even though its COMMIT acknowledgement is lost.
    store = _run_with_unavailable_verifier(
        store, database, tmp_path,
        lambda: store.finish_failure(
            first.attempt_key, "failure one", owner_run_id=first.owner_run_id,
            fencing_token=first.fencing_token,
        ),
    )
    row = store.get(first.attempt_key)
    assert row is not None and row.status is RecoveryAttemptStatus.FAILED
    assert row.attempt_count == 1 and row.fencing_token == 1
    assert row.last_error == "failure one" and row.owner_run_id is None

    # Authorization commits but cannot be verified until a fresh process opens the DB.
    store = _run_with_unavailable_verifier(
        store, database, tmp_path,
        lambda: store.authorize_retry(
            first.attempt_key, operator="operator-1", reason="reviewed failure one",
            checkpoint_fingerprint="checkpoint-v1",
        ),
    )
    authorized = store.get(first.attempt_key)
    assert authorized is not None and authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    assert authorized.authorized_by == "operator-1"
    assert authorized.authorization_reason == "reviewed failure one"
    assert authorized.checkpoint_fingerprint == "checkpoint-v1"
    assert authorized.attempt_count == 1 and authorized.fencing_token == 1

    # The authorized attempt itself is durable despite another lost acknowledgement.
    retry = _run_with_unavailable_verifier(
        store, database, tmp_path,
        lambda: store.begin_attempt(
            first.attempt_key, "second attempt", checkpoint_fingerprint="checkpoint-v1",
        ),
    )
    second = retry.get(first.attempt_key)
    assert second is not None and second.status is RecoveryAttemptStatus.IN_PROGRESS
    assert second.attempt_count == 2 and second.fencing_token == 2
    assert second.owner_run_id is not None and second.owner_run_id != first.owner_run_id
    assert second.authorized_by is None and second.authorization_reason is None
    assert second.last_error is None

    # A second durable failure and restart must not rewind the monotonically increasing token.
    retry = _run_with_unavailable_verifier(
        retry, database, tmp_path,
        lambda: retry.finish_failure(
            first.attempt_key, "failure two", owner_run_id=second.owner_run_id,
            fencing_token=second.fencing_token,
        ),
    )
    failed_again = retry.get(first.attempt_key)
    assert failed_again is not None and failed_again.status is RecoveryAttemptStatus.FAILED
    assert failed_again.attempt_count == 2 and failed_again.fencing_token == 2
    assert failed_again.last_error == "failure two"

    authorized_again = retry.authorize_retry(
        first.attempt_key, operator="operator-2", reason="reviewed failure two",
        checkpoint_fingerprint="checkpoint-v1",
    )
    third = retry.begin_attempt(
        first.attempt_key, "third attempt", checkpoint_fingerprint="checkpoint-v1",
    )
    assert authorized_again.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    assert third.status is RecoveryAttemptStatus.IN_PROGRESS
    assert third.attempt_count == 3 and third.max_attempts == 3
    assert third.fencing_token == 3

    terminal = retry.finish_failure(
        first.attempt_key, "attempt limit reached", owner_run_id=third.owner_run_id,
        fencing_token=third.fencing_token,
    )
    assert terminal.status is RecoveryAttemptStatus.FAILED
    assert terminal.attempt_count == 3 and terminal.fencing_token == 3
    with pytest.raises(RecoveryAttemptBlocked, match="maximum recovery attempts reached"):
        retry.authorize_retry(first.attempt_key, operator="operator-3", reason="must not exceed limit")
    with pytest.raises(RecoveryAttemptBlocked, match="maximum recovery attempts reached"):
        retry.begin_attempt(first.attempt_key, "must not launch a fourth attempt")
    final = retry.get(first.attempt_key)
    assert final is not None
    assert final.status is RecoveryAttemptStatus.FAILED
    assert final.attempt_count == final.max_attempts == 3
    assert final.fencing_token == 3
    # Retry authorization is intentionally one-shot and is cleared when consumed.
    assert final.authorized_by is None
    assert final.authorization_reason is None
    retry.close()
