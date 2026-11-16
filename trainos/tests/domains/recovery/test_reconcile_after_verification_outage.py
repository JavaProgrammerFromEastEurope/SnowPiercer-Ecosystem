"""A transient verification outage must be reconciled from durable state on restart."""
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _CommitThenLoseAcknowledgement:
    """Make the write durable, then simulate a lost COMMIT acknowledgement."""

    def __init__(self, connection):
        self.connection = connection
        self.raised = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        if not self.raised:
            self.raised = True
            raise sqlite3.OperationalError("simulated lost COMMIT acknowledgement")


def _make_verifier_temporarily_unavailable(store, tmp_path):
    original_path = store.database_path
    store.database_path = str(tmp_path / "temporarily-unavailable" / "journal.sqlite")
    return original_path


def test_restart_reconciles_durable_finish_after_verification_outage(tmp_path):
    database = tmp_path / "finish-durable.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    initial = store.begin_attempt("stage129-finish", "initial attempt")
    raw_connection = store._connection
    wrapper = _CommitThenLoseAcknowledgement(raw_connection)
    store._connection = wrapper
    original_path = _make_verifier_temporarily_unavailable(store, tmp_path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="lost COMMIT acknowledgement"):
            store.finish_success(
                initial.attempt_key, owner_run_id=initial.owner_run_id,
                fencing_token=initial.fencing_token,
            )
        assert wrapper.raised
        assert not raw_connection.in_transaction
    finally:
        store._connection = raw_connection
        store.database_path = original_path
        store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        durable = restarted.get(initial.attempt_key)
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.SUCCEEDED
        assert durable.attempt_count == 1
        assert durable.owner_run_id is None
        assert durable.lease_expires_at is None
        assert durable.fencing_token == initial.fencing_token
        with pytest.raises(RecoveryAttemptBlocked, match="no in-progress recovery attempt"):
            restarted.finish_success(
                initial.attempt_key, owner_run_id=initial.owner_run_id,
                fencing_token=initial.fencing_token,
            )
        unchanged = restarted.get(initial.attempt_key)
        assert unchanged is not None
        assert unchanged.status is RecoveryAttemptStatus.SUCCEEDED
        assert unchanged.attempt_count == 1
    finally:
        restarted.close()


def test_restart_reconciles_durable_retry_authorization_after_verification_outage(tmp_path):
    database = tmp_path / "retry-durable.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    initial = store.begin_attempt(
        "stage129-retry", "initial attempt", checkpoint_fingerprint="checkpoint-v1", max_attempts=2,
    )
    failed = store.finish_failure(
        initial.attempt_key, "controlled failure", owner_run_id=initial.owner_run_id,
        fencing_token=initial.fencing_token,
    )
    raw_connection = store._connection
    wrapper = _CommitThenLoseAcknowledgement(raw_connection)
    store._connection = wrapper
    original_path = _make_verifier_temporarily_unavailable(store, tmp_path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="lost COMMIT acknowledgement"):
            store.authorize_retry(
                initial.attempt_key, operator="stage129-operator", reason="reviewed retry",
                checkpoint_fingerprint="checkpoint-v1",
            )
        assert wrapper.raised
        assert not raw_connection.in_transaction
    finally:
        store._connection = raw_connection
        store.database_path = original_path
        store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        durable = restarted.get(initial.attempt_key)
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        assert durable.attempt_count == failed.attempt_count == 1
        assert durable.max_attempts == 2
        assert durable.fencing_token == initial.fencing_token
        assert durable.authorized_by == "stage129-operator"
        assert durable.authorization_reason == "reviewed retry"
        assert durable.checkpoint_fingerprint == "checkpoint-v1"
        with pytest.raises(RecoveryAttemptBlocked, match="retry can only be authorized"):
            restarted.authorize_retry(
                initial.attempt_key, operator="duplicate-operator", reason="duplicate request",
            )

        retry = restarted.begin_attempt(
            initial.attempt_key, "consume recovered authorization", checkpoint_fingerprint="checkpoint-v1",
        )
        assert retry.status is RecoveryAttemptStatus.IN_PROGRESS
        assert retry.attempt_count == 2
        assert retry.max_attempts == 2
        assert retry.fencing_token == initial.fencing_token + 1
        assert retry.owner_run_id != initial.owner_run_id
    finally:
        restarted.close()
