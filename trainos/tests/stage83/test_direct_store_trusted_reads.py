from datetime import datetime, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType,
    EventIntegrityAnchorStore, EventRegistry,
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


def _event(event_id: str = "e1") -> CommandEvent:
    return CommandEvent(
        event_id=event_id, command_id="cmd-1", event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"ok": True},
    )


def _stores(tmp_path, owned_stores):
    event_store = owned_stores(CommandEventStore, tmp_path / "events.sqlite")
    anchor_store = owned_stores(EventIntegrityAnchorStore, tmp_path / "anchors.sqlite")
    event_store.append(_event())
    anchor_store.create_anchor(event_store)
    return event_store, anchor_store


def test_direct_store_reads_blocked_without_anchor(tmp_path, owned_stores):
    store = owned_stores(CommandEventStore, tmp_path / "events.sqlite")
    anchors = owned_stores(EventIntegrityAnchorStore, tmp_path / "anchors.sqlite")
    store.enable_trusted_reads(anchors)
    with pytest.raises(RuntimeError, match="insufficient_data"):
        store.all_events()
    with pytest.raises(RuntimeError, match="insufficient_data"):
        store.get_events("cmd-1")


def test_direct_store_reads_pass_after_trusted_anchor(tmp_path, owned_stores):
    store, anchors = _stores(tmp_path, owned_stores)
    store.enable_trusted_reads(anchors)
    assert len(store.get_events("cmd-1")) == 1
    assert len(store.all_events()) == 1


def test_direct_store_read_detects_payload_tampering(tmp_path, owned_stores):
    store, anchors = _stores(tmp_path, owned_stores)
    store.enable_trusted_reads(anchors)
    with store._connection:
        store._connection.execute("UPDATE command_events SET payload_json = '{}' WHERE sequence = 1")
    with pytest.raises(RuntimeError, match="damaged"):
        store.all_events()


def test_registry_enables_direct_store_guard(tmp_path, owned_stores):
    store, anchors = _stores(tmp_path, owned_stores)
    EventRegistry(store=store, anchor_store=anchors, require_trusted_reads=True)
    assert len(store.get_events("cmd-1")) == 1
    with store._connection:
        store._connection.execute("UPDATE command_events SET payload_json = '{}' WHERE sequence = 1")
    with pytest.raises(RuntimeError, match="damaged"):
        store.get_events("cmd-1")


def test_same_database_path_rejected(tmp_path, owned_stores):
    store = owned_stores(CommandEventStore, tmp_path / "same.sqlite")
    anchors = owned_stores(EventIntegrityAnchorStore, tmp_path / "same.sqlite")
    with pytest.raises(ValueError, match="separate database paths"):
        store.enable_trusted_reads(anchors)
