"""Portable, authenticated event-integrity anchors for external storage.

HMAC provides authenticity only while the shared key remains secret. It is not
an asymmetric signature and does not itself deliver/store anchors remotely.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime
from typing import Any

from .event_integrity_anchor_store import EventIntegrityAnchor

_SCHEMA = "trainos.event-integrity-anchor.v1"
_DOMAIN = b"TrainOS:event-integrity-anchor:v1\x00"
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _validate_key(signing_key: bytes) -> None:
    if not isinstance(signing_key, bytes):
        raise TypeError("signing_key must be bytes")
    if len(signing_key) < 32:
        raise ValueError("signing_key must contain at least 32 bytes")


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_event_integrity_anchor(anchor: EventIntegrityAnchor, signing_key: bytes) -> str:
    """Serialize and authenticate one anchor as canonical JSON."""
    _validate_key(signing_key)
    if not isinstance(anchor, EventIntegrityAnchor):
        raise TypeError("anchor must be an EventIntegrityAnchor")
    if isinstance(anchor.event_sequence, bool) or anchor.event_sequence < 0:
        raise ValueError("event_sequence must be non-negative")
    if not isinstance(anchor.event_hash, str) or not _HASH_RE.fullmatch(anchor.event_hash):
        raise ValueError("event_hash must be a lowercase SHA-256 hex digest")
    if anchor.created_at.tzinfo is None or anchor.created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "anchor_id": anchor.anchor_id,
        "event_sequence": anchor.event_sequence,
        "event_hash": anchor.event_hash,
        "created_at": anchor.created_at.isoformat(),
        "algorithm": "HMAC-SHA256",
    }
    signature = hmac.new(signing_key, _DOMAIN + _canonical(payload), hashlib.sha256).hexdigest()
    return json.dumps({**payload, "signature": signature}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify_signed_event_integrity_anchor(serialized: str, signing_key: bytes) -> EventIntegrityAnchor:
    """Authenticate an exported anchor and return it; reject malformed or modified data."""
    _validate_key(signing_key)
    if not isinstance(serialized, str):
        raise TypeError("serialized must be a JSON string")
    try:
        envelope = json.loads(serialized)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("invalid anchor JSON") from exc
    required = {"schema", "anchor_id", "event_sequence", "event_hash", "created_at", "algorithm", "signature"}
    if not isinstance(envelope, dict) or set(envelope) != required:
        raise ValueError("invalid anchor envelope fields")
    if envelope["schema"] != _SCHEMA or envelope["algorithm"] != "HMAC-SHA256":
        raise ValueError("unsupported anchor schema or signature algorithm")
    signature = envelope["signature"]
    if not isinstance(signature, str) or not _HASH_RE.fullmatch(signature):
        raise ValueError("invalid anchor signature encoding")
    payload = {key: envelope[key] for key in required if key != "signature"}
    expected = hmac.new(signing_key, _DOMAIN + _canonical(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("anchor signature verification failed")
    anchor_id = envelope["anchor_id"]
    sequence = envelope["event_sequence"]
    if isinstance(anchor_id, bool) or not isinstance(anchor_id, int) or anchor_id < 1:
        raise ValueError("anchor_id must be a positive integer")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise ValueError("event_sequence must be a non-negative integer")
    event_hash = envelope["event_hash"]
    if not isinstance(event_hash, str) or not _HASH_RE.fullmatch(event_hash):
        raise ValueError("event_hash must be a lowercase SHA-256 hex digest")
    try:
        created_at = datetime.fromisoformat(envelope["created_at"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid anchor timestamp") from exc
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("anchor timestamp must be timezone-aware")
    return EventIntegrityAnchor(anchor_id, sequence, event_hash, created_at)
