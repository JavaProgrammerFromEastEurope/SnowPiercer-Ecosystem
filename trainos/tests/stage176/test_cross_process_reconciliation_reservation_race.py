"""Cross-process races between reconciliation and a fresh dispatch reservation."""
import multiprocessing

import pytest

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
)


def _race_reconcile_and_reserve(database_path, barrier, results, evidence):
    store = None
    try:
        store = CommandIdempotencyStore(database_path)
        barrier.wait(timeout=10)
        try:
            record = store.reconcile_not_executed(
                "race-key", evidence=evidence, execution_id="race-execution"
            )
            reconciliation = ("ok", record.status.value, record.dispatch_generation)
        except (IdempotencyConflict, ValueError) as exc:
            reconciliation = ("blocked", type(exc).__name__, "")
        reserved = store.reserve_dispatch("race-key")
        results.put((reconciliation, reserved))
    except BaseException as exc:  # surfaced in parent process assertions
        results.put(("ERROR", repr(exc)))
    finally:
        if store is not None:
            store.close()


def _prepare_unknown(path):
    store = CommandIdempotencyStore(path)
    store.claim("race-key", "set_route", {"route": "R-9"}, execution_id="race-execution")
    assert store.reserve_dispatch("race-key") is True
    store.mark_unknown("race-key", "acknowledgement lost")
    store.close()


def test_concurrent_processes_cannot_reuse_old_evidence_after_new_reservation(tmp_path):
    path = tmp_path / "cross-process-reconcile-race.sqlite3"
    _prepare_unknown(path)
    context = multiprocessing.get_context("spawn")
    workers = 6
    barrier = context.Barrier(workers)
    results = context.Queue()
    processes = [
        context.Process(
            target=_race_reconcile_and_reserve,
            args=(str(path), barrier, results, "verified-no-execution-receipt-v2"),
        )
        for _ in range(workers)
    ]
    for process in processes:
        process.start()
    try:
        for process in processes:
            process.join(timeout=25)
        assert all(not process.is_alive() for process in processes), "worker hung"
        assert [process.exitcode for process in processes] == [0] * workers
        outcomes = [results.get(timeout=3) for _ in processes]
        assert not any(outcome[0] == "ERROR" for outcome in outcomes), outcomes
        # Exactly one process may reserve the fresh generation.
        assert sum(bool(outcome[1]) for outcome in outcomes) == 1
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)

    store = CommandIdempotencyStore(path)
    try:
        record = store.get("race-key")
        assert record is not None
        assert record.status.value == "claimed"
        assert record.dispatch_started is True
        assert record.dispatch_generation == 2
        history = store._connection.execute(
            "SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation "
            "WHERE idempotency_key='race-key' ORDER BY sequence"
        ).fetchall()
        assert [(row["evidence"], row["decision"], row["dispatch_generation"]) for row in history] == [
            ("verified-no-execution-receipt-v2", "not_executed", 1)
        ]
        with pytest.raises(IdempotencyConflict, match="predates a later dispatch"):
            store.reconcile_not_executed(
                "race-key", evidence="verified-no-execution-receipt-v2", execution_id="race-execution"
            )
    finally:
        store.close()


def test_conflicting_evidence_race_preserves_single_reconciliation_record(tmp_path):
    path = tmp_path / "cross-process-conflicting-evidence.sqlite3"
    _prepare_unknown(path)
    context = multiprocessing.get_context("spawn")
    workers = 4
    barrier = context.Barrier(workers)
    results = context.Queue()
    evidence_values = ["evidence-A", "evidence-B", "evidence-C", "evidence-D"]
    processes = [
        context.Process(
            target=_race_reconcile_and_reserve,
            args=(str(path), barrier, results, evidence),
        )
        for evidence in evidence_values
    ]
    for process in processes:
        process.start()
    try:
        for process in processes:
            process.join(timeout=25)
        assert all(not process.is_alive() for process in processes), "worker hung"
        assert [process.exitcode for process in processes] == [0] * workers
        outcomes = [results.get(timeout=3) for _ in processes]
        assert not any(outcome[0] == "ERROR" for outcome in outcomes), outcomes
        assert sum(bool(outcome[1]) for outcome in outcomes) <= 1
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)

    store = CommandIdempotencyStore(path)
    try:
        history = store._connection.execute(
            "SELECT evidence, decision, dispatch_generation FROM command_idempotency_reconciliation "
            "WHERE idempotency_key='race-key' ORDER BY sequence"
        ).fetchall()
        assert len(history) == 1
        assert history[0]["decision"] == "not_executed"
        assert history[0]["dispatch_generation"] == 1
        assert history[0]["evidence"] in evidence_values
    finally:
        store.close()
