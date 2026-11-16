import json
from datetime import datetime, timezone

import pytest

from kernel.command.events.event_integrity_anchor_store import EventIntegrityAnchor
from kernel.command.events.signed_event_integrity_anchor import (
    sign_event_integrity_anchor,
    verify_signed_event_integrity_anchor,
)

KEY = b"stage79-test-key-that-is-at-least-32-bytes-long"
ANCHOR = EventIntegrityAnchor(3, 12, "a" * 64, datetime(2026, 10, 20, tzinfo=timezone.utc))


def test_signed_anchor_round_trip():
    serialized = sign_event_integrity_anchor(ANCHOR, KEY)
    restored = verify_signed_event_integrity_anchor(serialized, KEY)
    assert restored == ANCHOR
    assert json.loads(serialized)["algorithm"] == "HMAC-SHA256"


def test_wrong_key_rejected():
    serialized = sign_event_integrity_anchor(ANCHOR, KEY)
    with pytest.raises(ValueError, match="signature verification failed"):
        verify_signed_event_integrity_anchor(serialized, b"different-key-at-least-32-bytes-long!!")


def test_modified_sequence_rejected():
    envelope = json.loads(sign_event_integrity_anchor(ANCHOR, KEY))
    envelope["event_sequence"] += 1
    with pytest.raises(ValueError, match="signature verification failed"):
        verify_signed_event_integrity_anchor(json.dumps(envelope), KEY)


def test_modified_hash_rejected():
    envelope = json.loads(sign_event_integrity_anchor(ANCHOR, KEY))
    envelope["event_hash"] = "b" * 64
    with pytest.raises(ValueError, match="signature verification failed"):
        verify_signed_event_integrity_anchor(json.dumps(envelope), KEY)


def test_invalid_key_and_json_rejected():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        sign_event_integrity_anchor(ANCHOR, b"short")
    with pytest.raises(ValueError, match="invalid anchor JSON"):
        verify_signed_event_integrity_anchor("not-json", KEY)


def test_unknown_or_extra_envelope_fields_rejected():
    envelope = json.loads(sign_event_integrity_anchor(ANCHOR, KEY))
    envelope["unexpected"] = "value"
    with pytest.raises(ValueError, match="envelope fields"):
        verify_signed_event_integrity_anchor(json.dumps(envelope), KEY)


def test_naive_timestamp_and_bad_hash_cannot_be_signed():
    with pytest.raises(ValueError, match="timezone-aware"):
        sign_event_integrity_anchor(EventIntegrityAnchor(1, 0, "0" * 64, datetime(2026, 1, 1)), KEY)
    with pytest.raises(ValueError, match="SHA-256"):
        sign_event_integrity_anchor(EventIntegrityAnchor(1, 0, "bad", datetime.now(timezone.utc)), KEY)
