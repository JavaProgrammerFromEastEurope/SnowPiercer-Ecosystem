from tests.sqlite_resource_helpers import managed_sqlite_connection
from datetime import datetime, timezone
import sqlite3

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType,
    EventIntegrityAnchorStore, EventLogRecoveryGate, EventLogTrustStatus,
)


def event(event_id):
    return CommandEvent(event_id, "cmd", CommandEventType.COMMAND_STARTED,
                        datetime(2026, 1, 1, tzinfo=timezone.utc), {"id": event_id})


def stores(tmp_path):
    return (CommandEventStore(tmp_path / "events.sqlite"),
            EventIntegrityAnchorStore(tmp_path / "anchors.sqlite"))


def test_clean_restored_log_is_verified(tmp_path):
    events, anchors = stores(tmp_path)
    events.append(event("e1"))
    anchors.create_anchor(events)
    assessment = EventLogRecoveryGate.require_verified(events, anchors)
    assert assessment.status is EventLogTrustStatus.VERIFIED
    assert assessment.trusted_for_read
    events.close(); anchors.close()


def test_missing_anchor_means_insufficient_data_and_fails_closed(tmp_path):
    events, anchors = stores(tmp_path)
    assessment = EventLogRecoveryGate.assess(events, anchors)
    assert assessment.status is EventLogTrustStatus.INSUFFICIENT_DATA
    assert not assessment.trusted_for_read
    with pytest.raises(RuntimeError, match="insufficient_data"):
        EventLogRecoveryGate.require_verified(events, anchors)
    events.close(); anchors.close()


def test_tampered_log_is_damaged_and_fails_closed(tmp_path):
    events, anchors = stores(tmp_path)
    events.append(event("e1")); anchors.create_anchor(events)
    events.close()
    with managed_sqlite_connection(tmp_path / "events.sqlite") as db:
        db.execute("UPDATE command_events SET payload_json = ? WHERE event_id = ?", ('{"id":"changed"}', "e1"))
    events = CommandEventStore(tmp_path / "events.sqlite")
    assessment = EventLogRecoveryGate.assess(events, anchors)
    assert assessment.status is EventLogTrustStatus.DAMAGED
    assert not assessment.trusted_for_read
    with pytest.raises(RuntimeError, match="damaged"):
        EventLogRecoveryGate.require_verified(events, anchors)
    events.close(); anchors.close()


def test_rolled_back_log_is_damaged(tmp_path):
    events, anchors = stores(tmp_path)
    events.append(event("e1")); events.append(event("e2")); anchors.create_anchor(events)
    events.close()
    with managed_sqlite_connection(tmp_path / "events.sqlite") as db:
        db.execute("DELETE FROM command_events WHERE event_id = 'e2'")
    events = CommandEventStore(tmp_path / "events.sqlite")
    assessment = EventLogRecoveryGate.assess(events, anchors)
    assert assessment.status is EventLogTrustStatus.DAMAGED
    assert any(f["code"] == "anchored_tail_missing" for f in assessment.findings)
    events.close(); anchors.close()


def test_invalid_store_arguments_rejected(tmp_path):
    events, anchors = stores(tmp_path)
    with pytest.raises(TypeError):
        EventLogRecoveryGate.assess(object(), anchors)
    with pytest.raises(TypeError):
        EventLogRecoveryGate.assess(events, object())
    events.close(); anchors.close()
