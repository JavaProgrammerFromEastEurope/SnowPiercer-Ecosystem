"""External HMAC checkpoints for ledger database files.

The signing key must be supplied by the caller and stored outside the ledger
and checkpoint files (for example in a secrets manager or HSM-backed service).
This module does not manage or persist signing keys.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

from .models import LedgerError
from .store import FinancialLedger

_FORMAT = "trainos-ledger-checkpoint-v1"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _validate_key(key_id: str, key: bytes) -> None:
    if not isinstance(key_id, str) or not key_id or len(key_id) > 128:
        raise LedgerError("key_id must be a non-empty string of at most 128 characters")
    if not isinstance(key, bytes) or len(key) < 32:
        raise LedgerError("HMAC key must be bytes with at least 32 bytes of entropy")


def create_checkpoint(
    database: str | Path,
    manifest_path: str | Path,
    *,
    key_id: str,
    signing_key: bytes,
    sequence: int = 1,
    previous_manifest_sha256: str | None = None,
) -> dict[str, object]:
    """Validate a closed, standalone database and atomically write a signed manifest.

    The manifest is external to SQLite. Signing an active WAL database is not
    recommended; callers should checkpoint a backup produced by backup_to().
    """
    _validate_key(key_id, signing_key)
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise LedgerError("checkpoint sequence must be a positive integer")
    if previous_manifest_sha256 is not None and (
        not isinstance(previous_manifest_sha256, str)
        or len(previous_manifest_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in previous_manifest_sha256)
    ):
        raise LedgerError("previous manifest digest must be a lowercase SHA-256 hex digest")
    db_path = Path(database).resolve()
    manifest = Path(manifest_path).resolve()
    if not db_path.is_file() or db_path.stat().st_size == 0:
        raise LedgerError("database file is missing or empty")
    if db_path == manifest:
        raise LedgerError("manifest path must differ from database path")
    if not manifest.parent.is_dir():
        raise LedgerError("manifest parent directory must already exist")

    validation = FinancialLedger._validate_database_file(db_path)
    digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
    payload = {
        "format": _FORMAT,
        "key_id": key_id,
        "sequence": sequence,
        "previous_manifest_sha256": previous_manifest_sha256,
        "database_sha256": digest,
        "database_size_bytes": db_path.stat().st_size,
        "journal_count": int(validation["journal_count"]),
        "schema_version": int(validation["schema_version"]),
    }
    signature = hmac.new(signing_key, _canonical_json(payload), hashlib.sha256).hexdigest()
    document = {**payload, "signature_hmac_sha256": signature}
    encoded = _canonical_json(document) + b"\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{manifest.name}.", suffix=".tmp", dir=manifest.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, manifest)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"ok": True, "manifest_path": str(manifest), "manifest_sha256": hashlib.sha256(encoded).hexdigest(), **payload}


def verify_checkpoint(
    database: str | Path,
    manifest_path: str | Path,
    *,
    keyring: Mapping[str, bytes],
    minimum_sequence: int | None = None,
    expected_manifest_sha256: str | None = None,
) -> dict[str, object]:
    """Verify external manifest signature and exact database-file digest.

    `keyring` maps key IDs to trusted keys. During rotation, retain the previous
    verification key until all manifests signed with it have expired or been
    reissued under the new key.
    """
    if minimum_sequence is not None and (
        isinstance(minimum_sequence, bool) or not isinstance(minimum_sequence, int) or minimum_sequence < 1
    ):
        raise LedgerError("minimum_sequence must be a positive integer")
    if expected_manifest_sha256 is not None and (
        not isinstance(expected_manifest_sha256, str)
        or len(expected_manifest_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in expected_manifest_sha256)
    ):
        raise LedgerError("expected manifest digest must be a lowercase SHA-256 hex digest")
    db_path = Path(database).resolve()
    manifest = Path(manifest_path).resolve()
    if not db_path.is_file() or not manifest.is_file():
        raise LedgerError("database and checkpoint manifest must both exist")
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LedgerError("checkpoint manifest is not valid JSON") from exc
    if not isinstance(document, dict) or document.get("format") != _FORMAT:
        raise LedgerError("unsupported checkpoint manifest format")
    sequence = document.get("sequence", 1)
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise LedgerError("checkpoint sequence is invalid")
    if minimum_sequence is not None and sequence < minimum_sequence:
        raise LedgerError("checkpoint rollback detected: sequence is below trusted minimum")
    manifest_bytes = manifest.read_bytes()
    actual_manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if expected_manifest_sha256 is not None and not hmac.compare_digest(
        actual_manifest_digest, expected_manifest_sha256
    ):
        raise LedgerError("checkpoint rollback or replacement detected: manifest digest mismatch")
    key_id = document.get("key_id")
    key = keyring.get(key_id) if isinstance(key_id, str) else None
    if key is None:
        raise LedgerError("checkpoint signing key is not trusted")
    _validate_key(key_id, key)
    signature = document.get("signature_hmac_sha256")
    payload = {k: v for k, v in document.items() if k != "signature_hmac_sha256"}
    expected_signature = hmac.new(key, _canonical_json(payload), hashlib.sha256).hexdigest()
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected_signature):
        raise LedgerError("checkpoint signature verification failed")
    actual_size = db_path.stat().st_size
    actual_digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
    if payload.get("database_size_bytes") != actual_size or payload.get("database_sha256") != actual_digest:
        raise LedgerError("database does not match signed checkpoint")
    validation = FinancialLedger._validate_database_file(db_path)
    if payload.get("journal_count") != validation["journal_count"]:
        raise LedgerError("checkpoint journal count does not match database")
    if payload.get("schema_version") != validation["schema_version"]:
        raise LedgerError("checkpoint schema version does not match database")
    previous_digest = document.get("previous_manifest_sha256")
    if previous_digest is not None and (
        not isinstance(previous_digest, str)
        or len(previous_digest) != 64
        or any(ch not in "0123456789abcdef" for ch in previous_digest)
    ):
        raise LedgerError("previous manifest digest is invalid")
    return {
        "ok": True,
        "key_id": key_id,
        "sequence": sequence,
        "previous_manifest_sha256": previous_digest,
        "manifest_sha256": actual_manifest_digest,
        "database_sha256": actual_digest,
        "journal_count": validation["journal_count"],
        "schema_version": validation["schema_version"],
    }
