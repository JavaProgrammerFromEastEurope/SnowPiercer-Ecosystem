"""Crash-window tests for durable idempotency claims."""
import sqlite3

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyStatus,
)


class _CommitFaultProxy:
    """Inject one failure either before or after the underlying COMMIT."""

    def __init__(self, connection, *, commit_durable: bool):
        self._connection = connection
        self._commit_durable = commit_durable
        self._armed = True

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def commit(self):
        if not self._armed:
            return self._connection.commit()
        self._armed = False
        if self._commit_durable:
            self._connection.commit()
        raise sqlite3.OperationalError("simulated lost COMMIT acknowledgement")


def test_claim_commit_failure_before_durability_rolls_back_and_can_be_claimed(tmp_path):
    database = str(tmp_path / "claim-before-commit.sqlite3")
    store = CommandIdempotencyStore(database)
    raw_connection = store._connection
    store._connection = _CommitFaultProxy(raw_connection, commit_durable=False)
    try:
        try:
            store.claim("key-before", "inspect", {"component": "brake"}, execution_id="exec-before")
        except sqlite3.OperationalError as exc:
            assert "COMMIT acknowledgement" in str(exc)
        else:
            raise AssertionError("injected commit failure was not raised")
        assert not raw_connection.in_transaction
        assert raw_connection.execute(
            "SELECT COUNT(*) FROM command_idempotency WHERE idempotency_key=?", ("key-before",)
        ).fetchone()[0] == 0
    finally:
        store._connection = raw_connection
        store.close()

    restarted = CommandIdempotencyStore(database)
    try:
        claim = restarted.claim("key-before", "inspect", {"component": "brake"}, execution_id="exec-before")
        assert claim.created is True
        assert claim.record.status is IdempotencyStatus.CLAIMED
        assert claim.record.execution_id == "exec-before"
    finally:
        restarted.close()


def test_lost_commit_acknowledgement_after_durable_claim_reuses_existing_record(tmp_path):
    database = str(tmp_path / "claim-after-commit.sqlite3")
    store = CommandIdempotencyStore(database)
    raw_connection = store._connection
    store._connection = _CommitFaultProxy(raw_connection, commit_durable=True)
    try:
        try:
            store.claim("key-after", "set_mode", {"mode": "safe"}, execution_id="exec-after")
        except sqlite3.OperationalError as exc:
            assert "COMMIT acknowledgement" in str(exc)
        else:
            raise AssertionError("injected commit failure was not raised")
        assert not raw_connection.in_transaction
        persisted = raw_connection.execute(
            "SELECT status, execution_id FROM command_idempotency WHERE idempotency_key=?", ("key-after",)
        ).fetchone()
        assert persisted is not None
        assert persisted["status"] == "claimed"
        assert persisted["execution_id"] == "exec-after"
    finally:
        store._connection = raw_connection
        store.close()

    restarted = CommandIdempotencyStore(database)
    try:
        retry = restarted.claim("key-after", "set_mode", {"mode": "safe"}, execution_id="exec-after")
        assert retry.created is False
        assert retry.record.status is IdempotencyStatus.CLAIMED
        assert retry.record.execution_id == "exec-after"
        assert restarted._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        restarted.close()
