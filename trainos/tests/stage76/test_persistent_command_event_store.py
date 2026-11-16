from datetime import datetime, timezone, timedelta

import pytest

from kernel.command.events import CommandEvent, CommandEventStore, CommandEventType, EventRegistry


def event(event_id="e1", command_id="cmd", payload=None, timestamp=None):
    return CommandEvent(event_id, command_id, CommandEventType.COMMAND_STARTED,
                        timestamp or datetime(2026, 1, 1, tzinfo=timezone.utc), payload or {"x": 1})


def test_events_survive_store_and_registry_restart(tmp_path):
    path = tmp_path / "events.sqlite"
    store = CommandEventStore(path)
    registry = EventRegistry(max_events_per_command=1, store=store)
    registry.register(event("e1"))
    registry.register(event("e2", timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)))
    assert [e.event_id for e in registry.get_events("cmd")] == ["e1", "e2"]
    store.close()
    reopened = CommandEventStore(path)
    assert [e.event_id for e in reopened.all_events()] == ["e1", "e2"]
    assert reopened.all_events()[0].payload == {"x": 1}
    reopened.close()


def test_duplicate_identical_event_is_idempotent(tmp_path):
    store = CommandEventStore(tmp_path / "events.sqlite")
    item = event()
    store.append(item)
    store.append(item)
    assert len(store.all_events()) == 1
    store.close()


def test_conflicting_event_id_is_rejected(tmp_path):
    store = CommandEventStore(tmp_path / "events.sqlite")
    store.append(event())
    with pytest.raises(ValueError, match="conflicting duplicate event_id"):
        store.append(event(payload={"x": 2}))
    assert len(store.all_events()) == 1
    store.close()


def test_store_preserves_event_order_and_types(tmp_path):
    store = CommandEventStore(tmp_path / "events.sqlite")
    later = event("later", timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc))
    earlier = event("earlier", timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
    store.append(later)
    store.append(earlier)
    assert [e.event_id for e in store.all_events()] == ["earlier", "later"]
    assert all(e.event_type is CommandEventType.COMMAND_STARTED for e in store.all_events())
    store.close()


def test_registry_rejects_invalid_store():
    with pytest.raises(TypeError, match="CommandEventStore"):
        EventRegistry(store=object())


def test_persistent_registry_refuses_to_clear_append_only_history(tmp_path):
    store = CommandEventStore(tmp_path / "events.sqlite")
    registry = EventRegistry(store=store)
    registry.register(event())
    with pytest.raises(RuntimeError, match="append-only"):
        registry.clear()
    assert [item.event_id for item in store.all_events()] == ["e1"]
    store.close()
