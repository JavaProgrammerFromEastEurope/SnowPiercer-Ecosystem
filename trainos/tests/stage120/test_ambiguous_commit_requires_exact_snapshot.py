"""Ambiguous COMMIT acknowledgements are resolved only against the full row snapshot."""
import sqlite3

import pytest

from kernel.command.events import EventLogRecoveryAttemptStore, RecoveryAttemptStatus


class _CommitThenMutateAndRaise:
    """Commit locally, mutate a non-key field via another connection, lose the ack."""
    def __init__(self, connection, database, attempt_key, field, value):
        self.connection = connection
        self.database = str(database)
        self.attempt_key = attempt_key
        self.field = field
        self.value = value
        self.raised = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        if self.raised:
            return
        self.raised = True
        other = sqlite3.connect(self.database, timeout=2)
        try:
            other.execute(
                f"UPDATE recovery_attempts SET {self.field}=? WHERE attempt_key=?",
                (self.value, self.attempt_key),
            )
            other.commit()
        finally:
            other.close()
        raise sqlite3.OperationalError("simulated lost COMMIT acknowledgement after row divergence")


@pytest.mark.parametrize("field,value", [("reason", "unexpected concurrent edit"),
                                          ("checkpoint_fingerprint", "changed-fingerprint")])
def test_finish_does_not_accept_partial_row_match_after_ambiguous_commit(tmp_path, field, value):
    database = tmp_path / f"finish-divergence-{field}.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    initial = store.begin_attempt("stage120-finish", "stage120 exact row test")
    raw = store._connection
    store._connection = _CommitThenMutateAndRaise(raw, database, initial.attempt_key, field, value)
    try:
        with pytest.raises(sqlite3.OperationalError, match="row divergence"):
            store.finish_success(initial.attempt_key, owner_run_id=initial.owner_run_id,
                                 fencing_token=initial.fencing_token)
    finally:
        store._connection = raw
        store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        durable = restarted.get(initial.attempt_key)
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.SUCCEEDED
        assert getattr(durable, field) == value
        assert durable.owner_run_id is None
        assert durable.lease_expires_at is None
    finally:
        restarted.close()


def test_retry_authorization_does_not_accept_partial_row_match_after_ambiguous_commit(tmp_path):
    database = tmp_path / "retry-authorization-divergence.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    initial = store.begin_attempt("stage120-retry", "stage120 retry exact row test")
    failed = store.finish_failure(initial.attempt_key, "controlled failure",
                                  owner_run_id=initial.owner_run_id,
                                  fencing_token=initial.fencing_token)
    raw = store._connection
    store._connection = _CommitThenMutateAndRaise(
        raw, database, initial.attempt_key, "reason", "unexpected concurrent edit",
    )
    try:
        with pytest.raises(sqlite3.OperationalError, match="row divergence"):
            store.authorize_retry(initial.attempt_key, operator="test-operator", reason="reviewed retry")
    finally:
        store._connection = raw
        store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    try:
        durable = restarted.get(initial.attempt_key)
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
        assert durable.authorized_by == "test-operator"
        assert durable.reason == "unexpected concurrent edit"
        assert durable.attempt_count == failed.attempt_count
    finally:
        restarted.close()
