"""A lost COMMIT acknowledgement must not duplicate retry authorization."""
import sqlite3

import pytest

from kernel.command.events import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _CommitThenLoseAcknowledgement:
    """Commit durably, then simulate a driver error before acknowledging it."""

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


def test_ambiguous_retry_authorization_is_resolved_from_durable_row(tmp_path):
    database = tmp_path / "ambiguous-retry-authorization.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    try:
        first = store.begin_attempt(
            "stage127-authorization", "initial attempt", checkpoint_fingerprint="checkpoint-v1",
            max_attempts=2,
        )
        failed = store.finish_failure(
            first.attempt_key, "controlled failure", owner_run_id=first.owner_run_id,
            fencing_token=first.fencing_token,
        )
        raw_connection = store._connection
        wrapper = _CommitThenLoseAcknowledgement(raw_connection)
        store._connection = wrapper

        authorized = store.authorize_retry(
            first.attempt_key, operator="stage127-operator", reason="reviewed retry",
            checkpoint_fingerprint="checkpoint-v1",
        )

        assert wrapper.raised
        assert authorized.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        assert authorized.attempt_count == failed.attempt_count == 1
        assert authorized.max_attempts == 2
        assert authorized.fencing_token == first.fencing_token
        assert authorized.authorized_by == "stage127-operator"
        assert authorized.authorization_reason == "reviewed retry"
        assert authorized.checkpoint_fingerprint == "checkpoint-v1"
        store._connection = raw_connection

        # The committed authorization cannot be applied a second time. It does not
        # consume an attempt; only begin_attempt consumes the authorized retry.
        with pytest.raises(RecoveryAttemptBlocked, match="retry can only be authorized"):
            store.authorize_retry(
                first.attempt_key, operator="duplicate-operator", reason="duplicate request",
            )

        second = store.begin_attempt(
            first.attempt_key, "authorized retry", checkpoint_fingerprint="checkpoint-v1",
        )
        assert second.status is RecoveryAttemptStatus.IN_PROGRESS
        assert second.attempt_count == 2
        assert second.max_attempts == 2
        assert second.fencing_token == first.fencing_token + 1
        assert second.owner_run_id != first.owner_run_id
        assert second.authorized_by is None
        assert second.authorization_reason is None

        failed_again = store.finish_failure(
            first.attempt_key, "retry failed", owner_run_id=second.owner_run_id,
            fencing_token=second.fencing_token,
        )
        assert failed_again.attempt_count == 2
        with pytest.raises(RecoveryAttemptBlocked, match="maximum recovery attempts reached"):
            store.authorize_retry(
                first.attempt_key, operator="stage127-operator", reason="no attempts remain",
            )
    finally:
        store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        durable = restarted.get("stage127-authorization")
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.FAILED
        assert durable.attempt_count == 2
        assert durable.max_attempts == 2
        assert durable.fencing_token == first.fencing_token + 1
        assert durable.owner_run_id is None
        assert durable.lease_expires_at is None
        assert durable.last_error == "retry failed"
        assert durable.authorized_by is None
        assert durable.authorization_reason is None
    finally:
        restarted.close()
