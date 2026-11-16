"""Concurrent idempotency claims after a durable COMMIT lost its acknowledgement."""
from multiprocessing import get_context
import sqlite3

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
    IdempotencyStatus,
)


class _CommitThenLoseAck:
    def __init__(self, connection):
        self._connection = connection
        self._armed = True

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def commit(self):
        if self._armed:
            self._armed = False
            self._connection.commit()
            raise sqlite3.OperationalError("simulated lost COMMIT acknowledgement")
        return self._connection.commit()


def _claim_worker(database, barrier, result_queue, key, command, payload, execution_id):
    store = CommandIdempotencyStore(database)
    try:
        barrier.wait(timeout=15)
        try:
            claim = store.claim(key, command, payload, execution_id=execution_id)
        except IdempotencyConflict as exc:
            result_queue.put(("conflict", str(exc)))
        else:
            result_queue.put(("created" if claim.created else "existing",
                              claim.record.status.value, claim.record.execution_id))
    except BaseException as exc:
        result_queue.put(("error", repr(exc)))
        raise
    finally:
        store.close()


def _race(database, requests):
    context = get_context("spawn")
    barrier = context.Barrier(len(requests))
    queue = context.Queue()
    workers = [context.Process(target=_claim_worker,
                               args=(database, barrier, queue, *request)) for request in requests]
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join(timeout=25)
        assert all(not worker.is_alive() for worker in workers), "claim worker timed out"
        assert [worker.exitcode for worker in workers] == [0] * len(workers)
        results = [queue.get(timeout=5) for _ in workers]
        assert all(item[0] != "error" for item in results), results
        return results
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        queue.close()
        queue.join_thread()


def _seed_durable_claim_with_lost_ack(database):
    store = CommandIdempotencyStore(database)
    raw = store._connection
    store._connection = _CommitThenLoseAck(raw)
    try:
        try:
            store.claim("recovered-key", "inspect", {"component": "brake"}, execution_id="exec-158")
        except sqlite3.OperationalError as exc:
            assert "lost COMMIT acknowledgement" in str(exc)
        else:
            raise AssertionError("injected lost acknowledgement was not raised")
        assert not raw.in_transaction
    finally:
        store._connection = raw
        store.close()


def test_competing_processes_reuse_claim_after_lost_commit_ack(tmp_path):
    database = str(tmp_path / "durable-lost-ack.sqlite3")
    _seed_durable_claim_with_lost_ack(database)
    results = _race(database, [
        ("recovered-key", "inspect", {"component": "brake"}, "exec-158"),
        ("recovered-key", "inspect", {"component": "brake"}, "exec-158"),
    ])
    assert [item[0] for item in results] == ["existing", "existing"] or sorted(
        item[0] for item in results
    ) == ["existing", "existing"], results
    assert all(item[1:] == (IdempotencyStatus.CLAIMED.value, "exec-158") for item in results)
    store = CommandIdempotencyStore(database)
    try:
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
        assert store.get("recovered-key").status is IdempotencyStatus.CLAIMED
    finally:
        store.close()


def test_competing_mismatch_after_lost_commit_ack_cannot_replace_durable_claim(tmp_path):
    database = str(tmp_path / "durable-conflict.sqlite3")
    _seed_durable_claim_with_lost_ack(database)
    results = _race(database, [
        ("recovered-key", "inspect", {"component": "brake"}, "exec-158"),
        ("recovered-key", "open_valve", {"valve": "A"}, "exec-158"),
    ])
    assert sorted(item[0] for item in results) == ["conflict", "existing"], results
    store = CommandIdempotencyStore(database)
    try:
        record = store.get("recovered-key")
        assert record is not None
        assert record.command_name == "inspect"
        assert record.execution_id == "exec-158"
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        store.close()
