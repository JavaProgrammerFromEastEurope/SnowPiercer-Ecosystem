from tests.sqlite_resource_helpers import managed_sqlite_connection
import pytest
from datetime import datetime, timezone

from kernel.command.events import (
    CommandEvent, CommandEventStore, CommandEventType,
    EventIntegrityAnchorStore, sign_event_integrity_anchor,
)
from kernel.command.events.event_integrity_anchor_store import EventIntegrityAnchor

KEY = b"stage80-test-signing-key-32-bytes-minimum!!"


def event(event_id):
    return CommandEvent(event_id, "cmd", CommandEventType.COMMAND_STARTED,
                        datetime(2026, 1, 1, tzinfo=timezone.utc), {"id": event_id})


def signed(sequence, digest, anchor_id=1):
    return sign_event_integrity_anchor(
        EventIntegrityAnchor(anchor_id, sequence, digest, datetime(2026, 10, 20, tzinfo=timezone.utc)), KEY
    )


def test_verified_external_anchor_can_be_imported_and_checked(tmp_path):
    source = CommandEventStore(tmp_path / "source.sqlite")
    source.append(event("e1"))
    sequence, digest = source.integrity_head()
    portable = signed(sequence, digest)

    local = CommandEventStore(tmp_path / "local.sqlite")
    local.append(event("e1"))
    trust = EventIntegrityAnchorStore(tmp_path / "trust.sqlite")
    imported = trust.import_signed_anchor(portable, KEY)

    assert imported.event_sequence == 1
    assert imported.event_hash == digest
    assert trust.verify_against(local) == ()
    source.close(); local.close(); trust.close()


def test_import_rejects_bad_signature_without_persisting(tmp_path):
    trust = EventIntegrityAnchorStore(tmp_path / "trust.sqlite")
    with pytest.raises(ValueError, match="signature verification failed"):
        trust.import_signed_anchor(signed(1, "a" * 64), b"wrong-key-32-bytes-at-least-long!!!!")
    assert trust.latest() is None
    trust.close()


def test_import_rejects_rollback_to_older_sequence(tmp_path):
    trust = EventIntegrityAnchorStore(tmp_path / "trust.sqlite")
    trust.import_signed_anchor(signed(9, "a" * 64, anchor_id=9), KEY)
    with pytest.raises(ValueError, match="roll back"):
        trust.import_signed_anchor(signed(4, "b" * 64, anchor_id=4), KEY)
    assert trust.latest().event_sequence == 9
    trust.close()


def test_import_rejects_conflicting_hash_at_same_sequence(tmp_path):
    trust = EventIntegrityAnchorStore(tmp_path / "trust.sqlite")
    trust.import_signed_anchor(signed(4, "a" * 64), KEY)
    with pytest.raises(ValueError, match="conflicts"):
        trust.import_signed_anchor(signed(4, "b" * 64), KEY)
    assert len(trust.all_anchors()) == 1
    trust.close()


def test_reimport_same_checkpoint_is_idempotent(tmp_path):
    trust = EventIntegrityAnchorStore(tmp_path / "trust.sqlite")
    portable = signed(4, "a" * 64)
    first = trust.import_signed_anchor(portable, KEY)
    second = trust.import_signed_anchor(portable, KEY)
    assert first == second
    assert len(trust.all_anchors()) == 1
    trust.close()


def test_create_anchor_refuses_rolled_back_event_store(tmp_path):
    events = CommandEventStore(tmp_path / "events.sqlite")
    events.append(event("e1")); events.append(event("e2"))
    trust = EventIntegrityAnchorStore(tmp_path / "trust.sqlite")
    trust.create_anchor(events)
    events.close()
    import sqlite3
    with managed_sqlite_connection(tmp_path / "events.sqlite") as connection:
        connection.execute("DELETE FROM command_events WHERE event_id = 'e2'")
    # Opening the store does not fabricate a replacement anchor; creation must not lower trust.
    rolled_back = CommandEventStore(tmp_path / "events.sqlite")
    with pytest.raises(ValueError, match="older than the latest trusted anchor"):
        trust.create_anchor(rolled_back)
    rolled_back.close(); trust.close()


def test_verification_reports_tampering_even_when_anchored_head_hash_is_unchanged(tmp_path):
    import sqlite3
    events = CommandEventStore(tmp_path / "events.sqlite")
    events.append(event("e1")); events.append(event("e2"))
    trust = EventIntegrityAnchorStore(tmp_path / "trust.sqlite")
    trust.create_anchor(events)
    events.close()
    with managed_sqlite_connection(tmp_path / "events.sqlite") as connection:
        connection.execute("UPDATE command_events SET payload_json = ? WHERE event_id = 'e1'", ('{"id":"tampered"}',))
    tampered = CommandEventStore(tmp_path / "events.sqlite")
    codes = {finding["code"] for finding in trust.verify_against(tampered)}
    assert "event_store_integrity_failure" in codes
    assert "anchor_hash_mismatch" not in codes
    with pytest.raises(ValueError, match="integrity findings"):
        trust.create_anchor(tampered)
    tampered.close(); trust.close()
