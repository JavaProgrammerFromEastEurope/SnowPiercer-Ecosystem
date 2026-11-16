from datetime import datetime, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType,
    EventIntegrityAnchorStore,
)
from kernel.command.events.event_log_recovery_gate import EventLogRecoveryGate


@pytest.fixture
def owned_stores():
    """Own every SQLite-backed store through pytest teardown, including failure paths."""
    stores = []
    def create(cls, path):
        store = cls(path)
        stores.append(store)
        return store
    try:
        yield create
    finally:
        for store in reversed(stores):
            store.close()


def _event() -> CommandEvent:
    return CommandEvent(
        event_id="snapshot-event", command_id="snapshot-command",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"value": 1},
    )


def _trusted_stores(tmp_path, owned_stores):
    event_store = owned_stores(CommandEventStore, tmp_path / "events.sqlite")
    anchor_store = owned_stores(EventIntegrityAnchorStore, tmp_path / "anchors.sqlite")
    event_store.append(_event())
    anchor_store.create_anchor(event_store)
    event_store.enable_trusted_reads(anchor_store)
    return event_store, anchor_store


def test_trusted_read_starts_snapshot_before_trust_assessment(tmp_path, monkeypatch, owned_stores):
    store, _ = _trusted_stores(tmp_path, owned_stores)
    original = EventLogRecoveryGate.require_verified
    observed = []

    def inspect_transaction(event_store, anchor_store):
        observed.append(event_store._connection.in_transaction)
        return original(event_store, anchor_store)

    monkeypatch.setattr(EventLogRecoveryGate, "require_verified", staticmethod(inspect_transaction))
    assert len(store.all_events()) == 1
    assert observed == [True]
    assert not store._connection.in_transaction


def test_trusted_read_rolls_back_snapshot_when_gate_rejects(tmp_path, owned_stores):
    store = owned_stores(CommandEventStore, tmp_path / "events.sqlite")
    anchors = owned_stores(EventIntegrityAnchorStore, tmp_path / "anchors.sqlite")
    store.append(_event())
    store.enable_trusted_reads(anchors)

    with pytest.raises(RuntimeError, match="insufficient_data"):
        store.all_events()
    assert not store._connection.in_transaction


def test_trusted_read_uses_same_snapshot_for_verification_and_payload(tmp_path, owned_stores):
    store, _ = _trusted_stores(tmp_path, owned_stores)
    result = store.get_events("snapshot-command")
    assert result[0].payload == {"value": 1}
    assert not store._connection.in_transaction


def test_legacy_untrusted_read_does_not_leave_transaction_open(tmp_path, owned_stores):
    store = owned_stores(CommandEventStore, tmp_path / "events.sqlite")
    store.append(_event())
    assert len(store.all_events()) == 1
    assert not store._connection.in_transaction
