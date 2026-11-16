"""Injected SQLite COMMIT failures must preserve durable state and allow safe reuse."""
import sqlite3

import pytest

from kernel.command.events import EventLogRecoveryAttemptStore, RecoveryAttemptStatus


class _FailBeforeCommit:
    """Raise before SQLite receives COMMIT, leaving the transaction rollbackable."""

    def __init__(self, connection):
        self.connection = connection
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.calls += 1
        raise sqlite3.OperationalError("simulated storage I/O error before COMMIT")


class _CommitThenLoseAck:
    """Make COMMIT durable, then simulate a lost acknowledgement exactly once."""

    def __init__(self, connection):
        self.connection = connection
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.connection.commit()
        self.calls += 1
        if self.calls == 1:
            raise sqlite3.OperationalError("simulated lost COMMIT acknowledgement")


def test_precommit_io_error_rolls_back_and_store_can_finish_later(tmp_path):
    database = tmp_path / "precommit-io-error.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    try:
        initial = store.begin_attempt("stage150-precommit", "exercise pre-commit I/O error")
        raw = store._connection
        failing = _FailBeforeCommit(raw)
        store._connection = failing
        with pytest.raises(sqlite3.OperationalError, match="before COMMIT"):
            store.finish_success(
                initial.attempt_key,
                owner_run_id=initial.owner_run_id,
                fencing_token=initial.fencing_token,
            )
        assert failing.calls == 1
        assert not raw.in_transaction
        store._connection = raw

        unchanged = store.get(initial.attempt_key)
        assert unchanged is not None
        assert unchanged.status is RecoveryAttemptStatus.IN_PROGRESS
        assert unchanged.attempt_count == 1
        assert unchanged.owner_run_id == initial.owner_run_id
        assert unchanged.fencing_token == initial.fencing_token

        finished = store.finish_success(
            initial.attempt_key,
            owner_run_id=initial.owner_run_id,
            fencing_token=initial.fencing_token,
        )
        assert finished.status is RecoveryAttemptStatus.SUCCEEDED
        assert finished.attempt_count == 1
    finally:
        store.close()


def test_durable_commit_with_lost_ack_is_resolved_without_second_transition(tmp_path):
    database = tmp_path / "durable-lost-ack.sqlite"
    store = EventLogRecoveryAttemptStore(database)
    try:
        initial = store.begin_attempt("stage150-lost-ack", "exercise durable commit ambiguity")
        raw = store._connection
        wrapper = _CommitThenLoseAck(raw)
        store._connection = wrapper
        finished = store.finish_success(
            initial.attempt_key,
            owner_run_id=initial.owner_run_id,
            fencing_token=initial.fencing_token,
        )
        assert wrapper.calls == 1
        assert finished.status is RecoveryAttemptStatus.SUCCEEDED
        assert finished.attempt_count == 1
        assert not raw.in_transaction
        store._connection = raw

        durable = store.get(initial.attempt_key)
        assert durable is not None
        assert durable.status is RecoveryAttemptStatus.SUCCEEDED
        assert durable.attempt_count == 1
        with pytest.raises(Exception, match="no in-progress recovery attempt"):
            store.finish_success(
                initial.attempt_key,
                owner_run_id=initial.owner_run_id,
                fencing_token=initial.fencing_token,
            )
        after_duplicate = store.get(initial.attempt_key)
        assert after_duplicate is not None
        assert after_duplicate.status is RecoveryAttemptStatus.SUCCEEDED
        assert after_duplicate.attempt_count == 1
    finally:
        store.close()
