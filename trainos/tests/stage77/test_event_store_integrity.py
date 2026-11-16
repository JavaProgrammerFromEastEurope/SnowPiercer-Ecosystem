from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3
from datetime import datetime, timezone

from kernel.command.events import CommandEvent, CommandEventStore, CommandEventType


def make_event(event_id, payload=None):
    return CommandEvent(event_id, "cmd", CommandEventType.COMMAND_STARTED,
                        datetime(2026, 1, 1, tzinfo=timezone.utc), payload or {"ok": True})


def test_hash_chain_is_clean_and_survives_restart(tmp_path):
    path = tmp_path / "events.sqlite"
    store = CommandEventStore(path)
    store.append(make_event("e1"))
    store.append(make_event("e2", {"ok": False}))
    assert store.verify_integrity() == ()
    store.close()
    reopened = CommandEventStore(path)
    assert reopened.verify_integrity() == ()
    reopened.close()


def test_payload_tampering_is_detected(tmp_path):
    path = tmp_path / "events.sqlite"
    store = CommandEventStore(path)
    store.append(make_event("e1"))
    store.close()
    with managed_sqlite_connection(path) as connection:
        connection.execute("UPDATE command_events SET payload_json = ? WHERE event_id = ?", ('{"ok":false}', "e1"))
    reopened = CommandEventStore(path)
    assert any(item["code"] == "event_hash_mismatch" for item in reopened.verify_integrity())
    reopened.close()


def test_middle_row_deletion_is_detected(tmp_path):
    path = tmp_path / "events.sqlite"
    store = CommandEventStore(path)
    for event_id in ("e1", "e2", "e3"):
        store.append(make_event(event_id))
    store.close()
    with managed_sqlite_connection(path) as connection:
        connection.execute("DELETE FROM command_events WHERE event_id = 'e2'")
    reopened = CommandEventStore(path)
    codes = {item["code"] for item in reopened.verify_integrity()}
    assert "sequence_gap" in codes
    assert "previous_hash_mismatch" in codes
    reopened.close()


def test_duplicate_identical_event_does_not_change_chain(tmp_path):
    store = CommandEventStore(tmp_path / "events.sqlite")
    item = make_event("e1")
    store.append(item)
    store.append(item)
    assert store.verify_integrity() == ()
    store.close()
