"""Process-level races for durable command idempotency claims."""
from multiprocessing import get_context

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
)


def _claim_worker(database, barrier, result_queue, key, command, payload, execution_id=None):
    store = CommandIdempotencyStore(database)
    try:
        barrier.wait(timeout=15)
        try:
            claim = store.claim(key, command, payload, execution_id=execution_id)
        except IdempotencyConflict as exc:
            result_queue.put(("conflict", str(exc), key, command, payload, execution_id))
        else:
            result_queue.put(("claimed" if claim.created else "existing", claim.record.idempotency_key,
                              claim.record.command_name, claim.record.fingerprint,
                              claim.record.execution_id, key, command, payload, execution_id))
    except BaseException as exc:
        result_queue.put(("error", repr(exc)))
        raise
    finally:
        store.close()


def _run_race(database, requests):
    context = get_context("spawn")
    barrier = context.Barrier(len(requests))
    result_queue = context.Queue()
    workers = [context.Process(target=_claim_worker, args=(database, barrier, result_queue, *request))
               for request in requests]
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join(timeout=25)
        assert all(not worker.is_alive() for worker in workers), "claim worker process timed out"
        assert [worker.exitcode for worker in workers] == [0] * len(workers)
        results = [result_queue.get(timeout=5) for _ in workers]
        assert all(result[0] != "error" for result in results), results
        return results
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        result_queue.close()
        result_queue.join_thread()


def test_competing_processes_claim_same_key_and_payload_only_once(tmp_path):
    database = str(tmp_path / "same-command.sqlite3")
    results = _run_race(database, [
        ("shared-key", "set_mode", {"mode": "safe"}, "exec-safe"),
        ("shared-key", "set_mode", {"mode": "safe"}, "exec-safe"),
    ])
    assert sorted(result[0] for result in results) == ["claimed", "existing"], results
    store = CommandIdempotencyStore(database)
    try:
        record = store.get("shared-key")
        assert record is not None
        assert record.command_name == "set_mode"
        assert record.execution_id == "exec-safe"
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        store.close()


def test_competing_different_commands_with_same_key_preserve_one_winner(tmp_path):
    database = str(tmp_path / "conflicting-commands.sqlite3")
    results = _run_race(database, [
        ("shared-key", "open_valve", {"valve": "A"}),
        ("shared-key", "close_valve", {"valve": "A"}),
    ])
    assert sum(result[0] == "claimed" for result in results) == 1, results
    assert sum(result[0] == "conflict" for result in results) == 1, results
    store = CommandIdempotencyStore(database)
    try:
        record = store.get("shared-key")
        assert record is not None
        winner = next(result for result in results if result[0] == "claimed")
        assert record.command_name == winner[2]
        assert record.fingerprint == winner[3]
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        store.close()


def test_competing_keys_cannot_bind_same_execution_id(tmp_path):
    database = str(tmp_path / "execution-binding-race.sqlite3")
    results = _run_race(database, [
        ("key-a", "inspect", {"part": "brake"}, "shared-execution"),
        ("key-b", "inspect", {"part": "brake"}, "shared-execution"),
    ])
    assert sum(result[0] == "claimed" for result in results) == 1, results
    assert sum(result[0] == "conflict" for result in results) == 1, results
    store = CommandIdempotencyStore(database)
    try:
        rows = store._connection.execute(
            "SELECT idempotency_key, execution_id FROM command_idempotency"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["execution_id"] == "shared-execution"
    finally:
        store.close()
