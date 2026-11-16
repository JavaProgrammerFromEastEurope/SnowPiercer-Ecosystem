from tests.sqlite_resource_helpers import managed_sqlite_connection
from datetime import datetime, timezone
import sqlite3
import pytest
from kernel.command.events import CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore, EventRegistry


def event(event_id="e1"):
    return CommandEvent(event_id, "cmd", CommandEventType.COMMAND_STARTED,
                        datetime(2026, 1, 1, tzinfo=timezone.utc), {"id": event_id})


def test_trusted_read_mode_requires_persistent_stores(tmp_path):
    with pytest.raises(ValueError, match="require both"):
        EventRegistry(require_trusted_reads=True)
    store = CommandEventStore(tmp_path / "events.sqlite")
    with pytest.raises(ValueError, match="require both"):
        EventRegistry(store=store, require_trusted_reads=True)
    store.close()


def test_registry_blocks_reads_until_anchor_exists(tmp_path):
    store = CommandEventStore(tmp_path / "events.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "anchors.sqlite")
    store.append(event())
    registry = EventRegistry(store=store, anchor_store=anchors, require_trusted_reads=True)
    with pytest.raises(RuntimeError, match="insufficient_data"):
        registry.get_events("cmd")
    anchors.create_anchor(store)
    assert registry.get_events("cmd") == (event(),)
    assert registry.all_events() == (event(),)
    assert registry.get_latest("cmd") == event()
    store.close(); anchors.close()


def test_registry_blocks_reads_after_log_tampering(tmp_path):
    store_path, anchor_path = tmp_path / "events.sqlite", tmp_path / "anchors.sqlite"
    store = CommandEventStore(store_path)
    anchors = EventIntegrityAnchorStore(anchor_path)
    store.append(event()); anchors.create_anchor(store)
    registry = EventRegistry(store=store, anchor_store=anchors, require_trusted_reads=True)
    assert registry.get_latest("cmd") == event()
    store.close()
    with managed_sqlite_connection(store_path) as db:
        db.execute("UPDATE command_events SET payload_json = ? WHERE event_id = ?", ('{"id":"tampered"}', "e1"))
    store = CommandEventStore(store_path)
    registry = EventRegistry(store=store, anchor_store=anchors, require_trusted_reads=True)
    for read in (lambda: registry.get_events("cmd"), registry.all_events, lambda: registry.get_latest("cmd")):
        with pytest.raises(RuntimeError, match="damaged"):
            read()
    store.close(); anchors.close()


def test_default_registry_behavior_remains_compatible(tmp_path):
    store = CommandEventStore(tmp_path / "events.sqlite")
    registry = EventRegistry(store=store)
    store.append(event())
    assert registry.get_events("cmd") == (event(),)
    store.close()
