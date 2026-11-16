from tests.sqlite_resource_helpers import managed_sqlite_connection
import sqlite3

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType,
    EventIntegrityAnchorStore,
)
from datetime import datetime, timezone


def event(event_id, payload=None):
    return CommandEvent(
        event_id, "cmd", CommandEventType.COMMAND_STARTED,
        datetime(2026, 1, 1, tzinfo=timezone.utc), payload or {"value": event_id},
    )


def setup_stores(tmp_path):
    events = CommandEventStore(tmp_path / "events.sqlite")
    anchors = EventIntegrityAnchorStore(tmp_path / "trusted-anchors.sqlite")
    return events, anchors


def test_anchor_matches_clean_event_log_and_persists(tmp_path):
    events, anchors = setup_stores(tmp_path)
    events.append(event("e1"))
    anchor = anchors.create_anchor(events)
    assert anchor.event_sequence == 1
    assert anchor.created_at.tzinfo is not None
    assert anchors.verify_against(events) == ()
    anchors.close()
    anchors = EventIntegrityAnchorStore(tmp_path / "trusted-anchors.sqlite")
    assert anchors.latest() == anchor
    assert anchors.verify_against(events) == ()
    anchors.close()
    events.close()


def test_anchor_detects_tampering_before_anchored_head(tmp_path):
    events, anchors = setup_stores(tmp_path)
    events.append(event("e1"))
    events.append(event("e2"))
    anchors.create_anchor(events)
    events.close()
    with managed_sqlite_connection(tmp_path / "events.sqlite") as connection:
        connection.execute("UPDATE command_events SET payload_json = ? WHERE event_id = ?", ('{"value":"tampered"}', "e1"))
        connection.execute("UPDATE command_events SET previous_hash = ?, event_hash = ? WHERE event_id = ?", ("0" * 64, "f" * 64, "e1"))
        connection.execute("UPDATE command_events SET previous_hash = ?, event_hash = ? WHERE event_id = ?", ("f" * 64, "e" * 64, "e2"))
    events = CommandEventStore(tmp_path / "events.sqlite")
    findings = anchors.verify_against(events)
    assert "anchor_hash_mismatch" in {finding["code"] for finding in findings}
    assert "event_store_integrity_failure" in {finding["code"] for finding in findings}
    anchors.close()
    events.close()


def test_anchor_detects_deleted_anchored_tail(tmp_path):
    events, anchors = setup_stores(tmp_path)
    events.append(event("e1"))
    events.append(event("e2"))
    anchors.create_anchor(events)
    events.close()
    with managed_sqlite_connection(tmp_path / "events.sqlite") as connection:
        connection.execute("DELETE FROM command_events WHERE event_id = 'e2'")
    events = CommandEventStore(tmp_path / "events.sqlite")
    assert anchors.verify_against(events)[0]["code"] == "anchored_tail_missing"
    anchors.close()
    events.close()


def test_append_after_anchor_does_not_invalidate_previous_anchor(tmp_path):
    events, anchors = setup_stores(tmp_path)
    events.append(event("e1"))
    anchors.create_anchor(events)
    events.append(event("e2"))
    assert anchors.verify_against(events) == ()
    anchors.close()
    events.close()


def test_missing_anchor_is_reported_and_invalid_store_rejected(tmp_path):
    events, anchors = setup_stores(tmp_path)
    assert anchors.verify_against(events) == ({"code": "anchor_missing"},)
    with pytest.raises(TypeError):
        anchors.create_anchor(object())
    with pytest.raises(TypeError):
        anchors.verify_against(object())
    anchors.close()
    events.close()


def test_empty_log_anchor_detects_new_events(tmp_path):
    events, anchors = setup_stores(tmp_path)
    anchors.create_anchor(events)
    assert anchors.verify_against(events) == ()
    events.append(event("e1"))
    assert anchors.verify_against(events)[0]["code"] == "anchored_empty_log_changed"
    anchors.close()
    events.close()
