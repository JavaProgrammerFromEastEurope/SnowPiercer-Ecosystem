import sqlite3

import pytest

from kernel.command.events.event_log_recovery_attempt_store import (
    EventLogRecoveryAttemptStore,
    RecoveryAttemptBlocked,
    RecoveryAttemptStatus,
)


class _CommitFailOnce:
    """Connection proxy that injects one commit failure, then delegates normally."""

    def __init__(self, connection):
        self._connection = connection
        self.fail_next_commit = True

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def commit(self):
        if self.fail_next_commit:
            self.fail_next_commit = False
            raise sqlite3.OperationalError("simulated commit I/O failure")
        return self._connection.commit()


def _start(store, key="attempt"):
    attempt = store.begin_attempt(key, "stage110 test")
    return attempt.owner_run_id, attempt.fencing_token


def test_finish_update_trigger_failure_rolls_back_and_keeps_attempt_active(tmp_path):
    store = EventLogRecoveryAttemptStore(tmp_path / "journal.sqlite")
    owner, token = _start(store)
    store._connection.execute("""
        CREATE TRIGGER reject_terminal_status
        BEFORE UPDATE OF status ON recovery_attempts
        WHEN NEW.status = 'succeeded'
        BEGIN SELECT RAISE(ABORT, 'injected update failure'); END
    """)
    store._connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="injected update failure"):
        store.finish_success("attempt", owner_run_id=owner, fencing_token=token)

    current = store.get("attempt")
    assert current.status is RecoveryAttemptStatus.IN_PROGRESS
    assert current.owner_run_id == owner
    assert current.fencing_token == token
    assert not store._connection.in_transaction

    store._connection.execute("DROP TRIGGER reject_terminal_status")
    store._connection.commit()
    assert store.finish_success("attempt", owner_run_id=owner, fencing_token=token).status is RecoveryAttemptStatus.SUCCEEDED
    store.close()


def test_commit_failure_rolls_back_terminal_transition_and_allows_retry(tmp_path):
    store = EventLogRecoveryAttemptStore(tmp_path / "journal.sqlite")
    owner, token = _start(store)
    raw_connection = store._connection
    store._connection = _CommitFailOnce(raw_connection)

    with pytest.raises(sqlite3.OperationalError, match="commit I/O failure"):
        store.finish_success("attempt", owner_run_id=owner, fencing_token=token)

    current = store.get("attempt")
    assert current.status is RecoveryAttemptStatus.IN_PROGRESS
    assert current.owner_run_id == owner
    assert current.fencing_token == token
    assert not raw_connection.in_transaction

    assert store.finish_success("attempt", owner_run_id=owner, fencing_token=token).status is RecoveryAttemptStatus.SUCCEEDED
    store._connection = raw_connection
    store.close()


def test_retry_authorization_update_failure_does_not_authorize_retry(tmp_path):
    store = EventLogRecoveryAttemptStore(tmp_path / "journal.sqlite")
    owner, token = _start(store)
    store.finish_failure("attempt", "simulated recovery failure", owner_run_id=owner, fencing_token=token)
    store._connection.execute("""
        CREATE TRIGGER reject_retry_authorization
        BEFORE UPDATE OF status ON recovery_attempts
        WHEN NEW.status = 'retry_authorized'
        BEGIN SELECT RAISE(ABORT, 'injected authorization failure'); END
    """)
    store._connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="authorization failure"):
        store.authorize_retry("attempt", operator="operator", reason="reviewed failure")

    current = store.get("attempt")
    assert current.status is RecoveryAttemptStatus.FAILED
    assert current.authorized_by is None
    assert current.authorization_reason is None
    assert not store._connection.in_transaction

    store._connection.execute("DROP TRIGGER reject_retry_authorization")
    store._connection.commit()
    assert store.authorize_retry("attempt", operator="operator", reason="reviewed failure").status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    store.close()


def test_explicit_rollback_after_failed_transition_does_not_poison_connection(tmp_path):
    store = EventLogRecoveryAttemptStore(tmp_path / "journal.sqlite")
    owner, token = _start(store)
    with pytest.raises(RecoveryAttemptBlocked):
        store.finish_success("attempt", owner_run_id="stale-owner", fencing_token=token)
    assert not store._connection.in_transaction
    assert store.get("attempt").status is RecoveryAttemptStatus.IN_PROGRESS
    assert store.finish_success("attempt", owner_run_id=owner, fencing_token=token).status is RecoveryAttemptStatus.SUCCEEDED
    store.close()


class _CommitThenRaiseOnce:
    """Simulate a successful durable COMMIT whose caller receives an error."""

    def __init__(self, connection):
        self._connection = connection
        self.raise_after_commit = True

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def commit(self):
        self._connection.commit()
        if self.raise_after_commit:
            self.raise_after_commit = False
            raise sqlite3.OperationalError("simulated lost commit acknowledgement")


def test_finish_success_resolves_commit_exception_from_fresh_durable_read(tmp_path):
    database = tmp_path / "journal.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    owner, token = _start(store)
    raw_connection = store._connection
    store._connection = _CommitThenRaiseOnce(raw_connection)

    result = store.finish_success("attempt", owner_run_id=owner, fencing_token=token)

    assert result.status is RecoveryAttemptStatus.SUCCEEDED
    assert result.owner_run_id is None
    assert result.fencing_token == token
    store._connection = raw_connection
    store.close()

    # A new store/connection sees the durable terminal state; it must not try to
    # perform the same IN_PROGRESS -> SUCCEEDED transition a second time.
    restarted = EventLogRecoveryAttemptStore(database)
    assert restarted.get("attempt").status is RecoveryAttemptStatus.SUCCEEDED
    with pytest.raises(RecoveryAttemptBlocked, match="no in-progress"):
        restarted.finish_success("attempt", owner_run_id=owner, fencing_token=token)
    restarted.close()


def test_retry_authorization_resolves_commit_exception_from_fresh_durable_read(tmp_path):
    database = tmp_path / "journal.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    owner, token = _start(store)
    store.finish_failure("attempt", "simulated recovery failure", owner_run_id=owner, fencing_token=token)
    raw_connection = store._connection
    store._connection = _CommitThenRaiseOnce(raw_connection)

    result = store.authorize_retry(
        "attempt", operator="operator-1", reason="reviewed durable checkpoint",
    )

    assert result.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    assert result.authorized_by == "operator-1"
    assert result.authorization_reason == "reviewed durable checkpoint"
    store._connection = raw_connection
    store.close()

    restarted = EventLogRecoveryAttemptStore(database)
    durable = restarted.get("attempt")
    assert durable.status is RecoveryAttemptStatus.RETRY_AUTHORIZED
    assert durable.authorized_by == "operator-1"
    assert durable.authorization_reason == "reviewed durable checkpoint"
    restarted.close()
