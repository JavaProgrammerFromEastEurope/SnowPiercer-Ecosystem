"""Regression tests for repeated dispatch generations across prolonged outages."""

import pytest

from kernel.command.execution.command_idempotency_store import (
    CommandIdempotencyStore,
    IdempotencyConflict,
)


def test_multiple_generations_preserve_evidence_and_reject_stale_proofs(tmp_path):
    path = tmp_path / "multi-generation.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("long-outage-key", "set_route", {"route": "R-17"}, execution_id="exec-177")
    expected_history = []

    for generation in range(1, 4):
        assert store.reserve_dispatch("long-outage-key") is True
        record = store.get("long-outage-key")
        assert record is not None and record.dispatch_generation == generation
        store.mark_unknown("long-outage-key", f"acknowledgement missing for generation {generation}")
        proof = f"independent-not-executed-proof-generation-{generation}"
        resolved = store.reconcile_not_executed(
            "long-outage-key", evidence=proof, execution_id="exec-177"
        )
        assert resolved.status.value == "claimed"
        assert resolved.dispatch_generation == generation
        expected_history.append((proof, "not_executed", generation))

    # Begin a new attempt after the third explicit reconciliation.
    assert store.reserve_dispatch("long-outage-key") is True
    assert store.reserve_dispatch("long-outage-key") is False
    store.close()

    reopened = CommandIdempotencyStore(path)
    try:
        record = reopened.get("long-outage-key")
        assert record is not None
        assert record.dispatch_generation == 4
        assert record.dispatch_started is True
        history = reopened._connection.execute(
            "SELECT evidence, decision, dispatch_generation "
            "FROM command_idempotency_reconciliation "
            "WHERE idempotency_key=? ORDER BY sequence",
            ("long-outage-key",),
        ).fetchall()
        assert [tuple(row) for row in history] == expected_history
        with pytest.raises(IdempotencyConflict, match="predates a later dispatch"):
            reopened.reconcile_not_executed(
                "long-outage-key",
                evidence="independent-not-executed-proof-generation-3",
                execution_id="exec-177",
            )
        assert reopened.get("long-outage-key").dispatch_generation == 4
        assert reopened.get("long-outage-key").dispatch_started is True
    finally:
        reopened.close()


def test_unknown_after_latest_attempt_stays_blocked_until_fresh_reconciliation(tmp_path):
    path = tmp_path / "long-outage-unknown.sqlite3"
    store = CommandIdempotencyStore(path)
    store.claim("unknown-key", "set_route", {"route": "R-18"}, execution_id="exec-178")
    assert store.reserve_dispatch("unknown-key") is True
    store.mark_unknown("unknown-key", "executor acknowledgement unavailable")
    assert store.reserve_dispatch("unknown-key") is False
    store.close()

    reopened = CommandIdempotencyStore(path)
    try:
        record = reopened.get("unknown-key")
        assert record is not None
        assert record.status.value == "unknown"
        assert record.dispatch_generation == 1
        assert record.dispatch_started is True
        assert reopened.reserve_dispatch("unknown-key") is False
        resolved = reopened.reconcile_not_executed(
            "unknown-key", evidence="verified-no-execution-for-generation-1", execution_id="exec-178"
        )
        assert resolved.status.value == "claimed"
        assert resolved.dispatch_started is False
        assert reopened.reserve_dispatch("unknown-key") is True
        assert reopened.get("unknown-key").dispatch_generation == 2
    finally:
        reopened.close()
