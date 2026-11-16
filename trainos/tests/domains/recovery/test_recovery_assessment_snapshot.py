from datetime import datetime, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType, EventIntegrityAnchorStore,
    EventLogRecoveryGate, EventLogTrustStatus,
)


@pytest.fixture
def owned_sqlite_stores():
    """Close SQLite-backed stores on every exit, including assertion failures."""
    stores = []
    def open_store(store_type, path):
        store = store_type(path)
        stores.append(store)
        return store
    try:
        yield open_store
    finally:
        for store in reversed(stores):
            store.close()


def _event(event_id: str, value: int = 1) -> CommandEvent:
    return CommandEvent(
        event_id=event_id,
        command_id="recovery-assessment",
        event_type=CommandEventType.COMMAND_CREATED,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        payload={"value": value},
    )


def test_assessment_uses_one_event_snapshot_and_one_anchor_read(tmp_path, monkeypatch, owned_sqlite_stores):
    events = owned_sqlite_stores(CommandEventStore, tmp_path / "events.sqlite")
    anchors = owned_sqlite_stores(EventIntegrityAnchorStore, tmp_path / "anchors.sqlite")
    events.append(_event("e1"))
    anchors.create_anchor(events)

    original_snapshot = events.integrity_snapshot
    original_latest = anchors.latest
    snapshot_calls = []
    anchor_calls = []

    def tracked_snapshot():
        snapshot_calls.append(True)
        return original_snapshot()

    def tracked_latest():
        anchor_calls.append(True)
        return original_latest()

    monkeypatch.setattr(events, "integrity_snapshot", tracked_snapshot)
    monkeypatch.setattr(anchors, "latest", tracked_latest)

    assessment = EventLogRecoveryGate.assess(events, anchors)

    assert assessment.status is EventLogTrustStatus.VERIFIED
    assert assessment.event_sequence == 1
    assert assessment.anchor_sequence == 1
    assert snapshot_calls == [True]
    assert anchor_calls == [True]


def test_restored_event_database_with_missing_anchor_fails_closed(tmp_path, owned_sqlite_stores):
    events = owned_sqlite_stores(CommandEventStore, tmp_path / "restored-events.sqlite")
    events.append(_event("e1"))
    anchors = owned_sqlite_stores(EventIntegrityAnchorStore, tmp_path / "empty-anchors.sqlite")

    assessment = EventLogRecoveryGate.assess(events, anchors)

    assert assessment.status is EventLogTrustStatus.INSUFFICIENT_DATA
    assert assessment.trusted_for_read is False
    assert any(item["code"] == "anchor_missing" for item in assessment.findings)


def test_restored_older_event_database_is_detected_as_rollback(tmp_path, owned_sqlite_stores):
    import shutil

    live_path = tmp_path / "events.sqlite"
    events = owned_sqlite_stores(CommandEventStore, live_path)
    events.append(_event("e1"))
    events.close()

    # Capture an old, valid SQLite database before the later append and anchor.
    backup_path = tmp_path / "events-backup.sqlite"
    shutil.copy2(live_path, backup_path)
    anchors = owned_sqlite_stores(EventIntegrityAnchorStore, tmp_path / "anchors.sqlite")

    live = owned_sqlite_stores(CommandEventStore, live_path)
    live.append(_event("e2", 2))
    anchors.create_anchor(live)
    live.close()

    # Restore the older database while retaining the independently stored anchor.
    shutil.copy2(backup_path, live_path)
    restored = owned_sqlite_stores(CommandEventStore, live_path)
    try:
        assessment = EventLogRecoveryGate.assess(restored, anchors)
        assert assessment.status is EventLogTrustStatus.DAMAGED
        assert assessment.trusted_for_read is False
        assert any(item["code"] in {"anchored_tail_missing", "anchor_sequence_missing"}
                   for item in assessment.findings)
    finally:
        restored.close()
        anchors.close()


def test_assessment_reports_snapshot_head_not_a_separate_later_read(tmp_path, monkeypatch, owned_sqlite_stores):
    events = owned_sqlite_stores(CommandEventStore, tmp_path / "events.sqlite")
    anchors = owned_sqlite_stores(EventIntegrityAnchorStore, tmp_path / "anchors.sqlite")
    events.append(_event("e1"))
    anchors.create_anchor(events)
    original = events.integrity_snapshot

    def snapshot_then_append():
        snapshot = original()
        # Simulate an append after the captured snapshot. The assessment must report
        # the head contained in the snapshot, not perform a second head query.
        events.append(_event("e2", 2))
        return snapshot

    monkeypatch.setattr(events, "integrity_snapshot", snapshot_then_append)
    assessment = EventLogRecoveryGate.assess(events, anchors)

    assert assessment.event_sequence == 1
    assert events.integrity_head()[0] == 2
    assert assessment.status is EventLogTrustStatus.VERIFIED
