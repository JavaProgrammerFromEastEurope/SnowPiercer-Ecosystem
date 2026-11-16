"""A retrying caller must observe the durable idempotency state during reconciliation."""
from multiprocessing import get_context

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyStatus,
)


def _race_worker(database, barrier, queue, mode):
    store = CommandIdempotencyStore(database)
    try:
        barrier.wait(timeout=15)
        if mode == "reconcile":
            record = store.reconcile_completed(
                "key-160",
                {"outcome": "confirmed", "external_id": "device-op-160"},
                evidence="authoritative external status query",
                execution_id="exec-160",
            )
            queue.put((mode, record.status.value, record.result, record.execution_id))
        else:
            claim = store.claim(
                "key-160", "inspect_subsystem", {"subsystem": "brake-160"},
                execution_id="exec-160",
            )
            queue.put((mode, claim.created, claim.record.status.value,
                       claim.record.result, claim.record.execution_id))
    except BaseException as exc:
        queue.put(("error", mode, repr(exc)))
        raise
    finally:
        store.close()


def test_reconciliation_racing_with_reclaim_never_creates_second_operation(tmp_path):
    database = str(tmp_path / "stage160-race.sqlite3")
    seed = CommandIdempotencyStore(database)
    first = seed.claim(
        "key-160", "inspect_subsystem", {"subsystem": "brake-160"},
        execution_id="exec-160",
    )
    assert first.created
    seed.mark_unknown("key-160", "process restarted before external acknowledgement")
    seed.close()

    ctx = get_context("spawn")
    barrier = ctx.Barrier(2)
    queue = ctx.Queue()
    workers = [
        ctx.Process(target=_race_worker, args=(database, barrier, queue, mode))
        for mode in ("reconcile", "claim")
    ]
    for worker in workers:
        worker.start()
    try:
        for worker in workers:
            worker.join(timeout=25)
        assert all(not worker.is_alive() for worker in workers), "worker timed out"
        assert [worker.exitcode for worker in workers] == [0, 0]
        outcomes = [queue.get(timeout=5) for _ in workers]
        assert all(item[0] != "error" for item in outcomes), outcomes
        reconciled = next(item for item in outcomes if item[0] == "reconcile")
        claimed = next(item for item in outcomes if item[0] == "claim")
        assert reconciled[1] == IdempotencyStatus.COMPLETED.value
        assert reconciled[2] == {"outcome": "confirmed", "external_id": "device-op-160"}
        assert reconciled[3] == "exec-160"
        assert claimed[1] is False
        assert claimed[2] in {IdempotencyStatus.UNKNOWN.value, IdempotencyStatus.COMPLETED.value}
        assert claimed[4] == "exec-160"

        verify = CommandIdempotencyStore(database)
        try:
            record = verify.get("key-160")
            assert record is not None
            assert record.status is IdempotencyStatus.COMPLETED
            assert record.result == {"outcome": "confirmed", "external_id": "device-op-160"}
            assert record.execution_id == "exec-160"
            assert verify._connection.execute(
                "SELECT COUNT(*) FROM command_idempotency WHERE idempotency_key='key-160'"
            ).fetchone()[0] == 1
            assert verify._connection.execute(
                "SELECT COUNT(*) FROM command_idempotency_reconciliation WHERE idempotency_key='key-160'"
            ).fetchone()[0] == 1
        finally:
            verify.close()
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        queue.close()
        queue.join_thread()


def test_completed_command_claim_after_restart_returns_existing_result(tmp_path):
    database = tmp_path / "stage160-restart.sqlite3"
    store = CommandIdempotencyStore(database)
    store.claim("key-160", "inspect_subsystem", {"subsystem": "brake-160"}, execution_id="exec-160")
    store.complete("key-160", {"outcome": "confirmed"}, execution_id="exec-160")
    store.close()

    reopened = CommandIdempotencyStore(database)
    try:
        claim = reopened.claim(
            "key-160", "inspect_subsystem", {"subsystem": "brake-160"}, execution_id="exec-160"
        )
        assert claim.created is False
        assert claim.record.status is IdempotencyStatus.COMPLETED
        assert claim.record.result == {"outcome": "confirmed"}
        assert reopened._connection.execute("SELECT COUNT(*) FROM command_idempotency").fetchone()[0] == 1
    finally:
        reopened.close()
