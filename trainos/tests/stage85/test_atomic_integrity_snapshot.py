from datetime import datetime, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
)


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


def _event(event_id: str, value: int = 1) -> CommandEvent:
    return CommandEvent(
        event_id=event_id,
        command_id="snapshot-command",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        payload={"value": value},
    )


def test_integrity_snapshot_returns_consistent_head_and_hashes(tmp_path, owned_stores):
    store = owned_stores(CommandEventStore, tmp_path / "events.sqlite")
    store.append(_event("e1"))
    store.append(_event("e2", 2))

    findings, (head_sequence, head_hash), hashes = store.integrity_snapshot()

    assert findings == ()
    assert head_sequence == 2
    assert hashes[2] == head_hash
    assert len(hashes) == 2
    assert not store._connection.in_transaction


def test_anchor_creation_uses_atomic_integrity_snapshot(tmp_path, monkeypatch, owned_stores):
    store = owned_stores(CommandEventStore, tmp_path / "events.sqlite")
    store.append(_event("e1"))
    anchors = owned_stores(EventIntegrityAnchorStore, tmp_path / "anchors.sqlite")
    original = store.integrity_snapshot
    calls = []

    def tracked_snapshot():
        calls.append(True)
        return original()

    monkeypatch.setattr(store, "integrity_snapshot", tracked_snapshot)
    anchor = anchors.create_anchor(store)

    assert calls == [True]
    assert anchor.event_sequence == 1
    assert anchor.event_hash == store.integrity_head()[1]


def test_anchor_verification_uses_one_event_snapshot(tmp_path, monkeypatch, owned_stores):
    store = owned_stores(CommandEventStore, tmp_path / "events.sqlite")
    store.append(_event("e1"))
    anchors = owned_stores(EventIntegrityAnchorStore, tmp_path / "anchors.sqlite")
    anchors.create_anchor(store)
    original = store.integrity_snapshot
    calls = []

    def tracked_snapshot():
        calls.append(True)
        return original()

    monkeypatch.setattr(store, "integrity_snapshot", tracked_snapshot)
    assert anchors.verify_against(store) == ()
    assert calls == [True]


def test_integrity_snapshot_rolls_back_if_audit_fails(tmp_path, monkeypatch, owned_stores):
    store = owned_stores(CommandEventStore, tmp_path / "events.sqlite")

    def fail_audit():
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(store, "verify_integrity", fail_audit)
    with pytest.raises(RuntimeError, match="simulated audit failure"):
        store.integrity_snapshot()
    assert not store._connection.in_transaction
