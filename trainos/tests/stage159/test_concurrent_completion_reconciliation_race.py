"""Competing completion and reconciliation must never overwrite outcomes."""
from multiprocessing import get_context

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
    IdempotencyStatus,
)


def _reconcile_worker(database, barrier, result_queue, result, evidence):
    store = CommandIdempotencyStore(database)
    try:
        barrier.wait(timeout=15)
        try:
            record = store.reconcile_completed(
                "shared-key", result, evidence=evidence, execution_id="exec-159"
            )
        except IdempotencyConflict as exc:
            result_queue.put(("conflict", str(exc)))
        except BaseException as exc:
            result_queue.put(("error", repr(exc)))
            raise
        else:
            result_queue.put(("completed", record.status.value, record.result))
    finally:
        store.close()


def _race_reconciliations(database, candidates):
    context = get_context("spawn")
    barrier = context.Barrier(len(candidates))
    result_queue = context.Queue()
    workers = [
        context.Process(
            target=_reconcile_worker,
            args=(database, barrier, result_queue, result, evidence),
        )
        for result, evidence in candidates
    ]
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join(timeout=25)
        assert all(not worker.is_alive() for worker in workers), "reconciliation worker timed out"
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


def _seed_unknown(database):
    store = CommandIdempotencyStore(database)
    store.claim("shared-key", "inspect_brake", {"unit": "B-12"}, execution_id="exec-159")
    store.mark_unknown("shared-key", "external acknowledgement was lost")
    store.close()


def test_competing_conflicting_reconciliations_preserve_one_durable_result(tmp_path):
    database = str(tmp_path / "reconcile-race.sqlite3")
    _seed_unknown(database)
    outcomes = _race_reconciliations(database, [
        ({"inspection": "passed", "report": "A"}, "signed report A"),
        ({"inspection": "failed", "report": "B"}, "signed report B"),
    ])
    assert sorted(outcome[0] for outcome in outcomes) == ["completed", "conflict"], outcomes
    winning_result = next(outcome[2] for outcome in outcomes if outcome[0] == "completed")
    store = CommandIdempotencyStore(database)
    try:
        record = store.get("shared-key")
        assert record is not None
        assert record.status is IdempotencyStatus.COMPLETED
        assert record.result == winning_result
        assert record.execution_id == "exec-159"
        audit = store._connection.execute(
            "SELECT idempotency_key, evidence FROM command_idempotency_reconciliation ORDER BY sequence"
        ).fetchall()
        assert len(audit) == 1
        assert audit[0]["idempotency_key"] == "shared-key"
        assert audit[0]["evidence"] in {"signed report A", "signed report B"}
        assert store._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        store.close()


def test_competing_identical_reconciliations_do_not_duplicate_audit_evidence(tmp_path):
    database = str(tmp_path / "same-result-reconcile-race.sqlite3")
    _seed_unknown(database)
    result = {"inspection": "passed", "report": "same-report"}
    outcomes = _race_reconciliations(database, [
        (result, "independent verification A"),
        (result, "independent verification B"),
    ])
    assert [outcome[0] for outcome in outcomes] == ["completed", "completed"], outcomes
    store = CommandIdempotencyStore(database)
    try:
        record = store.get("shared-key")
        assert record is not None
        assert record.status is IdempotencyStatus.COMPLETED
        assert record.result == result
        audit = store._connection.execute(
            "SELECT evidence FROM command_idempotency_reconciliation WHERE idempotency_key=?",
            ("shared-key",),
        ).fetchall()
        # Duplicate same-result requests are idempotent; only the winning
        # state transition appends a reconciliation event.
        assert len(audit) == 1
        assert audit[0]["evidence"] in {"independent verification A", "independent verification B"}
    finally:
        store.close()
